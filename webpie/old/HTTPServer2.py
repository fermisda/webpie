import fnmatch, traceback, sys, time, os.path, stat, pprint, re, types
from socket import *
from pythreader import PyThread, synchronized, Task, TaskQueue, Processor, Primitive
from webpie import Response
try:
    from .uid import uid
except:
    from uid import uid     # if we run outside of the module

try:
    from .py3 import PY2, PY3, to_str, to_bytes
except:
    from py3 import PY2, PY3, to_str, to_bytes
    
Debug = False
        
class BodyFile(object):
    
    def __init__(self, buf, sock, length):
        self.Buffer = buf
        self.Sock = sock
        self.Remaining = length
        
    def get_chunk(self, n):
        if self.Buffer:
            chunk = self.Buffer[0]
            if len(chunk) > n:
                out = chunk[:n]
                self.Buffer[0] = chunk[n:]
            else:
                out = chunk
                self.Buffer = self.Buffer[1:]
        elif self.Sock is not None:
            out = self.Sock.recv(n)
            if not out: self.Sock = None
        return out
        
    MAXMSG = 8192
    
    def read(self, N = None):
        #print ("read({})".format(N))
        #print ("Buffer:", self.Buffer)
        if N is None:   N = self.Remaining
        out = []
        n = 0
        eof = False
        while not eof and (N is None or n < N):
            ntoread = self.MAXMSG if N is None else N - n
            chunk = self.get_chunk(ntoread)
            if not chunk:
                eof = True
            else:
                n += len(chunk)
                out.append(chunk)
        out = b''.join(out)
        if self.Remaining is not None:
            self.Remaining -= len(out)
        #print ("returning:[{}]".format(out))
        return out

class HTTPHeader(object):

    def __init__(self):
        self.Headline = None
        self.StatusCode = None
        self.StatusMessage = ""
        self.Method = None
        self.Protocol = None
        self.URI = None
        self.Path = None
        self.Query = ""
        self.OriginalURI = None
        self.Headers = {}
        self.Raw = b""
        self.Buffer = b""
        self.Complete = False
        self.Error = False
        
    def __str__(self):
        return "HTTPHeader(headline='%s', status=%s)" % (self.Headline, self.StatusCode)
        
    __repr__ = __str__

    def recv(self, sock, timeout = 15.0):
        tmo = sock.gettimeout()
        sock.settimeout(timeout)
        received = eof = False
        self.Error = None
        try:
            body = b''
            while not received and not self.Error and not eof:       # shutdown() will set it to None
                try:    
                    data = sock.recv(1024)
                except Exception as e:
                    self.Error = "Error in recv(): %s" % (e,)
                    data = b''
                if data:
                    received, error, body = self.consume(data)
                else:
                    eof = True
        finally:
            sock.settimeout(tmo)
        return received, body
        
    def replaceURI(self, uri):
        self.URI = self.Path = uri

    def is_server(self):
        return self.StatusCode is not None

    def is_client(self):
        return self.Method is not None
        
    def is_valid(self):
        return self.Error is None and self.Protocol and self.Protocol.upper().startswith("HTTP/")

    def is_final(self):
        return self.is_server() and self.StatusCode//100 != 1 or self.is_client()

    EOH_RE = re.compile(b"\r?\n\r?\n")
    MAXREAD = 100000

    def consume(self, inp):
        #print(self, ".consume(): inp:", inp)
        header_buffer = self.Buffer + inp
        match = self.EOH_RE.search(header_buffer)
        if not match:   
            self.Buffer = header_buffer
            error = False
            if len(header_buffer) > self.MAXREAD:
                self.Error = "Request is too long: %d" % (len(header_buffer),)
                error = True
            return False, error, b''
        i1, i2 = match.span()            
        self.Complete = True
        self.Raw = header = header_buffer[:i1]
        rest = header_buffer[i2:]
        headers = {}
        header = to_str(header)
        lines = [l.strip() for l in header.split("\n")]
        if lines:
            self.Headline = headline = lines[0]
            
            words = headline.split(" ", 2)
            #print ("HTTPHeader: headline:", headline, "    words:", words)
            if len(words) != 3:
                self.Error = "Can not parse headline. len(words)=%d" % (len(words),)
                return True, True, b''      # malformed headline
            if words[0].lower().startswith("http/"):
                self.StatusCode = int(words[1])
                self.StatusMessage = words[2]
                self.Protocol = words[0].upper()
            else:
                self.Method = words[0].upper()
                self.Protocol = words[2].upper()
                self.URI = self.OriginalURI = uri = words[1]
                self.setURI(uri)
                if '?' in uri:
                    # detach query part
                    self.Query = uri.split("?", 1)[1]
                    
            for l in lines[1:]:
                if not l:   continue
                try:   
                    h, b = tuple(l.split(':', 1))
                    headers[h.strip()] = b.strip()
                except: pass
            self.Headers = headers
        self.Buffer = b""
        return True, False, rest
        
    def setURI(self, uri):
        self.Path = self.URI = uri
        if '?' in uri:
            self.Path = uri.split("?",1)[0]

    def removeKeepAlive(self):
        if "Connection" in self.Headers:
            self.Headers["Connection"] = "close"

    def forceConnectionClose(self):
        self.Headers["Connection"] = "close"

    def headersAsText(self):
        headers = []
        for k, v in self.Headers.items():
            if isinstance(v, list):
                for vv in v:
                    headers.append("%s: %s" % (k, vv))
            else:
                headers.append("%s: %s" % (k, v))
        return "\r\n".join(headers) + "\r\n"

    def headline(self, original=False):
        if self.is_client():
            return "%s %s %s" % (self.Method, self.OriginalURI if original else self.URI, self.Protocol)
        else:
            return "%s %s %s" % (self.Protocol, self.StatusCode, self.StatusMessage)

    def as_text(self, original=False):
        return "%s\r\n%s" % (self.headline(original), self.headersAsText())

    def as_bytes(self, original=False):
        return to_bytes(self.as_text(original))


MIME_TYPES_BASE = {
    "gif":   "image/gif",
    "jpg":   "image/jpeg",
    "jpeg":   "image/jpeg",
    "js":   "text/javascript",
    "html":   "text/html",
    "txt":   "text/plain",
    "css":  "text/css"
}


class RequestHandle(object):
    def __init__(self, cid, sock, caddr, ssl_info):
        self.CID = cid
        self.Sock = sock
        self.CAddr = caddr
        self.Header = None
        self.SSLInfo = ssl_info
        self.Body = b""
        self.ResponseStatus = None
        self.OutBuffer = ""
        
    def start_response(self, status, headers):
        self.ResponseStatus = status.split()[0]
        out = ["HTTP/1.1 " + status]
        for h,v in headers:
            if h != "Connection":
                out.append("%s: %s" % (h, v))
        out.append("Connection: close")     # can not handle keep-alive
        self.OutBuffer = "\r\n".join(out) + "\r\n\r\n"
    
    def close(self):
        if self.Sock is not None:
            self.Sock.close()
            self.Sock = None
            
    def __del__(self):
        self.close()

"""
server_config = {
    [
        name:   
        app:        WPApp
        match:      re
        rewrite:    re
            ---------
        #prefix:     prefix
        #replace_prefix:    replace_with
        max_connections:
        max_queud
        timeout
        logging:    bool
        log_file:   file (has write())
    ]
}
"""

class Servlet(Processor):

    def __init__(self, name, app, match, rewrite, 
                prefix, replace_prefix,
                max_connections, max_queued, transfer_timeout, logger=None):
        Processor.__init__(self, max_connections, max_queued, delegate=self, add_timeout = 0)
        assert prefix is None or match is None
        self.Logger = logger
        self.Name = name
        self.App = app
        self.MatchRE = re.compile(match) if match is not None else None
        self.Rewrite = rewrite
        self.Prefix = prefix
        self.ReplacePrefix = replace_prefix
    
    def debug(self, *parts):
        self.Logger.debug(f"{self.Name}", "(d)", *parts)
        
    def error(self, *parts):
        self.Logger.error(f"{self.Name}", "(E)", *parts)
        
    @staticmethod
    def from_config(cfg, logger=None):
        return HTTPServlet(
            cfg.get("name","wsgi_app"),
            cfg["app"],
            cfg.get("match"),
            cfg.get("rewrite"),
            cfg.get("prefix"),
            cfg.get("replace_prefix"),
            cfg.get("max_connections", 10),
            cfg.get("max_queued", 10),
            cfg.get("timeout", 30),
            logger
        )
        
    def match_uri(self, uri):
        if self.MatchRE is not None:
            self.MatchRE.match(uri) is not None
        elif self.Prefix is not None:
            return uri.startswith(self.Prefix)
        else:
            return True

    def rewrite_uri(self, uri):
        if self.MatchRE is not None and self.Rewrite is not None:
            uri = self.MatchRE.sub(self.Rewrite, uri)
        elif self.Prefix is not None and self.ReplacePrefix is not None:
            uri = self.ReplacePrefix + uri[len(self.Prefix):]
        return uri
        
    def addToBody(self, data):
        if PY3:   data = to_bytes(data)
        #print ("addToBody:", data)
        self.Body.append(data)

    def parseQuery(self, query):
        out = {}
        for w in query.split("&"):
            if w:
                words = w.split("=", 1)
                k = words[0]
                if k:
                    v = None
                    if len(words) > 1:  v = words[1]
                    if k in out:
                        old = out[k]
                        if type(old) != type([]):
                            old = [old]
                            out[k] = old
                        out[k].append(v)
                    else:
                        out[k] = v
        return out
        
    def format_x509_name(self, x509_name):
        components = [(to_str(k), to_str(v)) for k, v in x509_name.get_components()]
        return "/".join(f"{k}={v}" for k, v in components)
        
    def x509_names(self, ssl_info):
        import OpenSSL.crypto as crypto
        subject, issuer = None, None
        if ssl_info is not None:
            cert_bin = ssl_info.getpeercert(True)
            if cert_bin is not None:
                x509 = crypto.load_certificate(crypto.FILETYPE_ASN1,cert_bin)
                if x509 is not None:
                    subject = self.format_x509_name(x509.get_subject())
                    issuer = self.format_x509_name(x509.get_issuer())
        return subject, issuer

    def process(self, handle):        
        #self.debug("processRequest()")

        request = handle.Header
        
        request.setURI(self.rewrite_uri(request.URI))
        
        self.debug("%s request: %s" % (handle.CID, request.Headline))
        
        env = dict(
            REQUEST_METHOD = request.Method.upper(),
            PATH_INFO = request.Path,
            SCRIPT_NAME = "",
            SERVER_PROTOCOL = request.Protocol,
            QUERY_STRING = request.Query
        )
        env["wsgi.url_scheme"] = "http"
        
        ssl_info = handle.SSLInfo

        if ssl_info != None:
            subject, issuer = self.x509_names(ssl_info)
            env["SSL_CLIENT_S_DN"] = subject
            env["SSL_CLIENT_I_DN"] = issuer
            env["wsgi.url_scheme"] = "https"
        
        if request.Headers.get("Expect") == "100-continue":
            self.CSock.sendall(b'HTTP/1.1 100 Continue\n\n')
                
        env["query_dict"] = self.parseQuery(request.Query)
        
        #print ("processRequest: env={}".format(env))
        body_length = None
        for h, v in request.Headers.items():
            h = h.lower()
            if h == "content-type": env["CONTENT_TYPE"] = v
            elif h == "host":
                words = v.split(":",1)
                words.append("")    # default port number
                env["HTTP_HOST"] = v
                env["SERVER_NAME"] = words[0]
                env["SERVER_PORT"] = words[1]
            elif h == "content-length": 
                env["CONTENT_LENGTH"] = body_length = int(v)
            else:
                env["HTTP_%s" % (h.upper().replace("-","_"),)] = v

        env["wsgi.input"] = BodyFile(handle.Body, handle.Sock, body_length)
        
        out = []
        
        try:
            out = self.App(env, handle.start_response)    
        except:
            self.error("%s %s" % (handle.CID, traceback.format_exc()))
            handle.start_response("500 Error", 
                            [("Content-Type","text/plain")])
            handle.OutBuffer = error = traceback.format_exc()
            self.logError(handle.CAddr, error)
        
        if handle.OutBuffer:      # from start_response
            handle.Sock.sendall(to_bytes(handle.OutBuffer))
            
        byte_count = 0

        for line in out:
            line = to_bytes(line)
            try:    handle.Sock.sendall(line)
            except Exception as e:
                self.logError(self.CAddr, "error sending body: %s" % (e,))
                break
            byte_count += len(line)
        else:
            self.logRequest(handle, byte_count)

        handle.close()
        self.debug("%s done" % (handle.CID))
        
    def logRequest(self, handle, byte_count):
        header = handle.Header
        display_uri = header.URI if header.URI == header.OriginalURI else \
            "%s (-> %s)" % (header.OriginalURI, header.Path)
        self.Logger.log(self.Name, handle.CID, "%s:%d" % handle.CAddr, header.Method, display_uri, handle.ResponseStatus, byte_count)
        
    def start_response(self, status, headers):
        self.debug("start_response(%s)" % (status,))
        self.ResponseStatus = status.split()[0]
        out = ["HTTP/1.1 " + status]
        for h,v in headers:
            if h != "Connection":
                out.append("%s: %s" % (h, v))
        out.append("Connection: close")     # can not handle keep-alive
        self.OutBuffer = "\r\n".join(out) + "\r\n\r\n"
        
    def itemFailed(self, handle, exc_type, exc_value, tb):
        self.debug("request failed:", "".join(traceback.format_exception(exc_type, exc_value, tb)))
        
    def itemDiscarded(self, handle):
        pass
        
    def itemProcessed(self, handle):
        pass
        
class Dispatcher(object):
    
    def __init__(self, servlets, logger):
        self.Servlets = servlets
        self.Logger = logger

    def add(self, handle):
        header = handle.Header
        uri = header.URI
        for servlet in self.Servlets:
            if servlet.match_uri(uri):
                try:    servlet.add(handle)
                except RuntimeError:
                    handle.Sock.sendall(b"HTTP/1.1 503 Application queue is full\n\n")
                    handle.close()
                break
        else:
            handle.Sock.sendall(b"HTTP/1.1 404 Not found\n\n")
            handle.close()

class RequestReader(Processor):
    
    def __init__(self, dispatcher, logger, max_readers = 10, timeout = 30.0, max_queued = 100):
        Processor.__init__(self, max_readers, max_queued, output = dispatcher)
        self.Timeout = timeout
        self.Logger = logger
        
    def process(self, handle):
        header = HTTPHeader()
        request_received, body = header.recv(handle.Sock, self.Timeout)

        if not request_received or not header.is_valid() or not header.is_client() or header.Error:
            handle.close()
            return None
        else:
            handle.Header = header
            handle.Body = body
            return handle

class Listener(PyThread):
    
    def __init__(self, port, server, reader, logger):
        PyThread.__init__(self)
        self.Reader = reader
        self.Logger = logger
        self.Port = port
        self.Server = server
        
    def debug(self, *parts):
        self.Logger.debug("Listener", *parts)

    def run(self):
        self.Sock = socket(AF_INET, SOCK_STREAM)
        self.Sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.Sock.bind(('', self.Port))
        self.Sock.listen(10)
        while True:
            csock = None
            caddr = ('-','-')
            csock, caddr = self.Sock.accept()
            cid = uid()
            self.debug("%s connection accepted from %s:%s" % (cid, caddr[0], caddr[1]))
            wrapped_sock, ssl_info = self.Server.wrap_socket(csock)
            handle = RequestHandle(cid, wrapped_sock, caddr, ssl_info)
            try:
                self.Reader.add(handle)
            except RuntimeError:
                self.debug("% reader queue is full" % (cid,))
                wrapped_sock.sendall(b"HTTP/1.1 503 Server queue is full\n\n")
                wrapped_sock.close()
            

    def taskEnded(self, reader):
        handle = reader.Handle
        if handle is not None:
            try:    self.Dispatcher.add(handle)
            except RuntimeError:
                self.debug("%s failed to send request to the dispatcher" % (handle.CID,))
        else:
            self.debug("%s reader ended with error: %s" % (reader.CID, reader.Error))
        
    def taskFailed(self, reader, exc_type, exc_value, tb):
        self.debug("%s reader failed: %s" % (reader.CID, 
            "".join(traceback.format_exception(exc_type, exc_value, tb))))
        
                
class Logger(object):
    def __init__(self, logging = False, log_file = None, debug=None):
        self.Logging = logging
        self.LogFile = log_file
        self.Debug = debug
        
    def log(self, who, *parts, sep=" ", end="\n"):
        if self.Logging:
            msg = sep.join([str(p) for p in parts])
            if who:
                msg = f"[{who}] {msg}"
            msg = "%s: %s%s" % (time.ctime(), msg, end)
            self.LogFile.write(msg)
            if self.LogFile is sys.stdout:
                self.LogFile.flush()
                
    def debug(self, who, *parts, sep=" ", end="\n"):
        if self.Debug:
            who = who or "debug"
            msg = "%s: [%s] %s%s" % (time.ctime(), who, sep.join([str(p) for p in parts]), end)
            self.Debug.write(msg)
            if self.Debug is sys.stdout:
                self.Debug.flush()
                
    def error(self, who, *parts, sep=" ", end="\n"):
        msg = "%s: [%s] %s%s" % (time.ctime(), who, sep.join([str(p) for p in parts]), end)
        sys.stderr.write(msg)
        sys.stderr.flush()
        if not self.Debug is sys.stderr:
            self.Debug.write(msg)
            if self.Debug is sys.stdout:
                self.Debug.flush()
            
class HTTPServer2(object):
    
    def __init__(self, port, servlets, 
            max_request_readers = 10,
            max_queued_readers = 10,
            reader_timeout = 30.0,
            logging = False, log_file = None, debug=None):
        self.Logger = Logger(logging, log_file, debug)
        
        if isinstance(servlets[0], dict):
            servlets = [Servlet.from_config(d) for d in servlets]
        
        for s in servlets:
            s.Logger = self.Logger
        
        self.Dispatcher = Dispatcher(servlets, self.Logger)
        self.RequestReader = RequestReader(self.Dispatcher, self.Logger, max_readers=max_request_readers,
            timeout = reader_timeout, max_queued = max_queued_readers)
        self.Listener = Listener(port, self, self.RequestReader, self.Logger)

    def start(self):
        self.Listener.start()
        
    def join(self):
        self.Listener.join()

    def wrap_socket(self, sock):
        return sock, None


"""       
apps = 
    [
       { name:   
        app:        WPApp
        match:      re
        rewrite:    re
            ---------
        #prefix:     prefix
        #replace_prefix:    replace_with
        max_connections:
        max_queud
        timeout
        logging:    bool
        log_file:   file (has write())
    }
    ]
""" 

class HTTPServer(object):
    
    def __init__(self, port, app,
                app_name = None,
                uri_pattern=None, rewrite_pattern=None,
                prefix = None, replace_prefix = None,
                timeout = 10.0, max_connections = 100, 
                enabled = True, max_queued = 100,
                logging = False, log_file = None, debug=None):
        
        if app_name is None:
            app_name = app.__name__ + "()" if isinstance(app, types.FunctionType) else app.__class__.__name__

        servlet = Servlet(app_name, app, 
            uri_pattern, rewrite_pattern, 
            prefix, replace_prefix,
            max_connections, max_queued, timeout)
        if logging and log_file is None:    log_file = sys.stdout
        self.Server2 = HTTPServer2(port, [servlet], logging=logging, log_file=log_file, debug=debug)
        
    def start(self):
        self.Server2.start()
        
    def join(self):
        self.Server2.join()

class HTTPSServer(HTTPServer):

    def __init__(self, port, app, certfile, keyfile, verify="none", ca_file=None, password=None, **args):
        HTTPServer.__init__(self, port, app, **args)
        import ssl
        #self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS)
        self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.SSLContext.load_cert_chain(certfile, keyfile, password=password)
        if ca_file is not None:
            self.SSLContext.load_verify_locations(cafile=ca_file)
        self.SSLContext.verify_mode = {
                "none":ssl.CERT_NONE,
                "optional":ssl.CERT_OPTIONAL,
                "required":ssl.CERT_REQUIRED
            }[verify]
        self.SSLContext.load_default_certs()
        #print("Context created")
        
    def wrap_socket(self, sock):
        ssl_socket = self.SSLContext.wrap_socket(sock, server_side=True)
        return ssl_socket, ssl_socket
        
def run_server(port, app, **args):
    srv = HTTPServer(port, app, **args)
    srv.start()
    srv.join()
    

if __name__ == '__main__':

    def app(env, start_response):
        start_response("200 OK", [("Content-Type","text/plain")])
        return (
            "%s = %s\n" % (k,v) for k, v in env.items()
            )

    run_server(8000, app, logging=True, debug=sys.stdout, prefix="/app/", replace_prefix="/")
