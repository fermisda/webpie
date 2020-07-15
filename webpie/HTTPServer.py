import fnmatch, traceback, sys, time, os.path, stat, pprint, re
from socket import *
from pythreader import PyThread, synchronized, Task, TaskQueue
from webpie import Response
from .uid import uid

from .py3 import PY2, PY3, to_str, to_bytes
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

    def recv(self, sock):
        tmo = sock.gettimeout()
        sock.settimeout(5.0)
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
        self.URI = uri

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
                self.Path = self.URI = self.OriginalURI = uri = words[1]
                if '?' in uri:
                    # detach query part
                    self.Path, self.Query = uri.split("?", 1)
                    
            for l in lines[1:]:
                if not l:   continue
                try:   
                    h, b = tuple(l.split(':', 1))
                    headers[h.strip()] = b.strip()
                except: pass
            self.Headers = headers
        self.Buffer = b""
        return True, False, rest

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

            
class HTTPConnection(Task):

    MAXMSG = 100000

    def __init__(self, cid, server, csock, caddr):
        Task.__init__(self)
        self.CID = cid
        self.Server = server
        self.CAddr = caddr
        self.CSock = csock
        self.Body = []
        self.OutBuffer = ""
        self.ResponseStatus = None
        self.Started = None
        self.debug("created. client: %s:%s" % caddr)
        
    def __str__(self):
        return "[connection %s]" % (self.CID, )
        
    def debug(self, msg):
        self.Server.debug("%s: %s" % (self, msg))

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
                
    def processRequest(self, request):        
        #self.debug("processRequest()")
        
        self.debug("processRequest(): %s" % (request,))

        env = dict(
            REQUEST_METHOD = request.Method.upper(),
            PATH_INFO = request.Path,
            SCRIPT_NAME = "",
            SERVER_PROTOCOL = request.Protocol,
            QUERY_STRING = request.Query
        )
        
        if request.Headers.get("Expect") == "100-continue":
            self.CSock.sendall(b'HTTP/1.1 100 Continue\n\n')
                
        env["wsgi.url_scheme"] = "http"
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

        env["wsgi.input"] = BodyFile(self.Body, self.CSock, body_length)
        
        
        try:
            out = self.Server.wsgi_app(env, self.start_response)    
        except:
            self.debug("error in wsgi_app: %s" % (traceback.format_exc(),))
            self.start_response("500 Error", 
                            [("Content-Type","text/plain")])
            self.OutBuffer = error = traceback.format_exc()
            self.Server.log_error(self.CAddr, error)
        
        
        if self.OutBuffer:      # from start_response
            self.CSock.sendall(to_bytes(self.OutBuffer))
            
        byte_count = 0

        for line in out:
            line = to_bytes(line)
            try:    self.CSock.sendall(line)
            except Exception as e:
                self.Server.log_error(self.CAddr, "error sending body: %s" % (e,))
                break
            byte_count += len(line)
        else:
            self.Server.log(self.CAddr, request.Method, request.URI, self.ResponseStatus, byte_count)

        self.CSock.close()
        self.debug("done. socket closed")

    def start_response(self, status, headers):
        self.debug("start_response(%s)" % (status,))
        self.ResponseStatus = status.split()[0]
        out = ["HTTP/1.1 " + status]
        for h,v in headers:
            if h != "Connection":
                out.append(f"{h}: {v}")
        out.append("Connection: close")     # can not handle keep-alive
        self.OutBuffer = "\r\n".join(out) + "\r\n\r\n"
        
    def run(self):
        try:
            self.debug("started")
            self.Started = time.time()
            self.CSock.settimeout(self.Server.Timeout)        
            try:
                self.CSock = self.Server.wrap_socket(self.CSock)
                self.debug("socket wrapped")
            except Exception as e:
                self.debug("Error wrapping socket: %s" % (e,))
            else:
                request = HTTPHeader()
                request_received, body = request.recv(self.CSock)
        
                if not request_received or not request.is_valid() or not request.is_client():
                    # header not received - end
                    self.debug("request not received or invalid or not client request: %s" % (request,))
                    if request.Error:
                        self.debug("request read error: %s" % (request.Error,))
                    self.CSock.close()
                    return
            
                if body:
                    self.addToBody(body)

                self.processRequest(request)
        finally:
            # make sure to close the underlying socket
            try:    self.CSock.close()
            except: pass

class HTTPServer(PyThread):

    MIME_TYPES_BASE = {
        "gif":   "image/gif",
        "jpg":   "image/jpeg",
        "jpeg":   "image/jpeg",
        "js":   "text/javascript",
        "html":   "text/html",
        "txt":   "text/plain",
        "css":  "text/css"
    }

    def __init__(self, port, app, remove_prefix = "", url_pattern="*", max_connections = 100, 
                timeout = 10.0,
                enabled = True, max_queued = 100,
                logging = False, log_file = None, debug=None):
        PyThread.__init__(self)
        #self.debug("Server started")
        self.Port = port
        self.Timeout = timeout
        self.WSGIApp = app
        self.Match = url_pattern
        self.Enabled = False
        self.Logging = logging
        self.LogFile = sys.stdout if log_file is None else log_file
        self.Connections = TaskQueue(max_connections, capacity = max_queued)
        self.RemovePrefix = remove_prefix
        if enabled:
            self.enableServer()
        self.Debug = debug
        
    @synchronized
    def debug(self, msg):
        #print("debug: %s %s" % (type(self.Debug), self.Debug))
        if self.Debug:
            self.Debug.write("%s: [debug] %s\n" % (time.ctime(), msg))
            if self.Debug is sys.stdout:
                self.Debug.flush()
        
    @synchronized
    def log(self, caddr, method, uri, status, bytes_sent):
        if self.Logging:
            self.LogFile.write("{}: {}:{} {} {} {} {}\n".format(
                    time.ctime(), caddr[0], caddr[1], method, uri, status, bytes_sent
            ))
            if self.LogFile is sys.stdout:
                self.LogFile.flush()
            
    @synchronized
    def log_error(self, caddr, message):
        if self.Logging:
            self.LogFile.write("{}: {}:{} {}\n".format(
                    time.ctime(), caddr[0], caddr[1], message
            ))
            if self.LogFile is sys.stdout:
                self.LogFile.flush()
        else:
            print ("{}: {}:{} {}\n".format(
                    time.ctime(), caddr[0], caddr[1], message
            ))
        

    def urlMatch(self, path):
        return fnmatch.fnmatch(path, self.Match)
        
    def rewritePath(self, path):
        if self.RemovePrefix and path.startswith(self.RemovePrefix):
            path = path[len(self.RemovePrefix):]
        return path

    def wsgi_app(self, env, start_response):
        return self.WSGIApp(env, start_response)
        
    @synchronized
    def enableServer(self, backlog = 5):
        self.Enabled = True
                
    @synchronized
    def disableServer(self):
        self.Enabled = False

    def connectionClosed(self, conn):
        pass
            
    @synchronized
    def connectionCount(self):
        return len(self.Connections)    
            
    def run(self):
        self.Sock = socket(AF_INET, SOCK_STREAM)
        self.Sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.Sock.bind(('', self.Port))
        self.Sock.listen(10)
        while True:
            self.debug("--- accept loop port=%d start" % (self.Port,))
            csock = None
            caddr = ('-','-')
            try:
                csock, caddr = self.Sock.accept()
                cid = uid()
                self.debug("connection %s accepted from %s:%s" % (cid, caddr[0], caddr[1]))
                conn = self.createConnection(cid, csock, caddr)
                if conn is not None:
                        self.Connections << conn
                        self.debug("%s from %s queued. Active/queued connections: %d/%d" % (
                            conn, caddr, len(self.Connections.activeTasks()), len(self.Connections.waitingTasks())))
            except Exception as exc:
                self.debug("connection processing error: %s" % (traceback.format_exc(),))
                self.log_error(caddr, "Error processing connection: %s" % (exc,))
                if csock is not None:
                    try:    csock.close()
                    except: pass
            self.debug("--- accept loop port=%d end" % (self.Port,))

    # overridable
    def createConnection(self, cid, csock, caddr):
        return HTTPConnection(cid, self, csock, caddr)
        
    def wrap_socket(self, sock):
        return sock

                
class HTTPSServer(HTTPServer):

    def __init__(self, port, app, certfile, keyfile, ca_file=None, password=None, **args):
        HTTPServer.__init__(self, port, app, **args)
        import ssl
        #self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS)
        self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.SSLContext.load_cert_chain(certfile, keyfile, password=password)
        if ca_file is not None:
            self.SSLContext.load_verify_locations(cafile=ca_file)
        self.SSLContext.verify_mode = ssl.CERT_NONE
        self.SSLContext.load_default_certs()
        #print("Context created")
        
    def wrap_socket(self, sock):
        return self.SSLContext.wrap_socket(sock, server_side=True)
            

def run_server(port, app, url_pattern="*"):
    srv = HTTPServer(port, app, url_pattern=url_pattern)
    srv.start()
    srv.join()
    

if __name__ == '__main__':

    def app(env, start_response):
        start_response("200 OK", [("Content-Type","text/plain")])
        return (
            "%s = %s\n" % (k,v) for k, v in env.items()
            )

    run_server(8000, app)
