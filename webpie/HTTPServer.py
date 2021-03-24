import fnmatch, traceback, sys, time, os.path, stat, pprint, re, signal, importlib

from socket import *
from pythreader import PyThread, synchronized, Task, TaskQueue, Primitive
from webpie import Response
from .uid import uid
from .WPApp import WPApp
from .logs import Logged

from .py3 import PY2, PY3, to_str, to_bytes
        
        
class BodyFile(object):
    
    def __init__(self, buf, sock, length):
        #print("BodyFile: buf:", buf)
        self.Buffer = buf
        self.Sock = sock
        self.Remaining = length
        
    def get_chunk(self, n):
        #print("get_chunk: Buffer:", self.Buffer)
        if self.Buffer:
            out = self.Buffer[:n]
            self.Buffer = self.Buffer[n:]
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
        self.OriginalURI = None
        self.Headers = {}
        self.Raw = b""
        self.Buffer = b""
        self.Complete = False
        self.Error = None
        
    def __str__(self):
        return "HTTPHeader(headline='%s', status=%s)" % (self.Headline, self.StatusCode)
        
    __repr__ = __str__

    def recv(self, sock):
        tmo = sock.gettimeout()
        sock.settimeout(15.0)
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
                self.URI = self.OriginalURI = words[1]
                    
            for l in lines[1:]:
                if not l:   continue
                try:   
                    h, b = tuple(l.split(':', 1))
                    headers[h.strip()] = b.strip()
                except: pass
            self.Headers = headers
        self.Buffer = b""
        return True, False, rest

    def path(self):
        return self.URI.split("?",1)[0]

    def query(self):
        if '?' in self.URI:
             return self.URI.split("?",1)[1]
        else:
             return ""

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
        
class RequestProcessor(Logged):
    
    def __init__(self, wsgi_app, request, logger):
        self.App = wsgi_app
        self.Request = request
        self.OutBuffer = ""
        self.ResponseStatus = None
        Logged.__init__(self, request.Id, logger)
        
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
        

    def run(self):        
        request = self.Request
        header = request.HTTPHeader
        ssl_info = request.SSLInfo
        csock = request.CSock
        
        env = dict(
            REQUEST_METHOD = header.Method.upper(),
            PATH_INFO = header.path(),
            SCRIPT_NAME = "",
            SERVER_PROTOCOL = header.Protocol,
            QUERY_STRING = header.query()
        )
        env["wsgi.url_scheme"] = "http"

        if ssl_info != None:
            subject, issuer = self.x509_names(ssl_info)
            env["SSL_CLIENT_S_DN"] = subject
            env["SSL_CLIENT_I_DN"] = issuer
            env["wsgi.url_scheme"] = "https"
        
        if header.Headers.get("Expect") == "100-continue":
            csock.sendall(b'HTTP/1.1 100 Continue\n\n')
                
        env["query_dict"] = self.parseQuery(header.query())
        
        #print ("processRequest: env={}".format(env))
        body_length = None
        for h, v in header.Headers.items():
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

        env["wsgi.input"] = BodyFile(request.Body, csock, body_length)
        
        out = []
        
        try:
            #print("env:")
            #for k, v in env.items():
            #    print(k,":",v)
            out = self.App(env, self.start_response)    
        except:
            self.log_error("error in wsgi_app: %s" % (traceback.format_exc(),))
            self.start_response("500 Error", 
                            [("Content-Type","text/plain")])
            self.OutBuffer = error = traceback.format_exc()
            self.log_error(request.CAddr, error)
        
        if self.OutBuffer:      # from start_response
            csock.sendall(to_bytes(self.OutBuffer))
            
        byte_count = 0

        for line in out:
            line = to_bytes(line)
            try:    csock.sendall(line)
            except Exception as e:
                self.log_error(request.CAddr, "error sending body: %s" % (e,))
                break
            byte_count += len(line)
        else:
            self.log('%s:%s :%s %s %s -> %s %s %s %s' % 
                (   request.CAddr[0], request.CAddr[1], request.ServerPort, 
                    header.Method, header.OriginalURI, 
                    request.AppName, header.path(), 
                    self.ResponseStatus, byte_count
                )
            )

        request.close()
        self.debug("done. socket closed")

    def start_response(self, status, headers):
        self.debug("start_response(%s)" % (status,))
        self.ResponseStatus = status.split()[0]
        out = ["HTTP/1.1 " + status]
        for h,v in headers:
            if h != "Connection":
                out.append("%s: %s" % (h, v))
        out.append("Connection: close")     # can not handle keep-alive
        self.OutBuffer = "\r\n".join(out) + "\r\n\r\n"

class DirectApplication(Logged):
    
    def __init__(self, app, logger=None):
        
        assert isinstance(app, WPApp)
        
        import importlib
        
        Logged.__init__(self, f"[app {app.__class__.__name__}]", logger)
        self.Name = app.__class__.__name__
        self.WPApp = app
        
    def accept(self, request):
        p = RequestProcessor(self.WPApp, request, self.Logger)
        request.AppName = self.Name
        p.run()
        return True

class Request(object):
    
    def __init__(self, port, csock, caddr):
        self.Id = uid()
        self.ServerPort = port
        self.CSock = csock
        self.CAddr = caddr
        self.HTTPHeader = None
        self.Body = b''
        self.SSLInfo = None     
        self.AppName = None
        
    def close(self):
        if self.CSock is not None:
            try:    self.CSock.close()
            except: pass
            self.CSock = None
        self.SSLInfo = None
        
class RequestReader(Task, Logged):

    MAXMSG = 100000

    def __init__(self, dispatcher, request, socket_wrapper, timeout, logger):
        Task.__init__(self)
        self.Request = request
        Logged.__init__(self, f"[reader {request.Id}]", logger, debug=True)
        self.SocketWrapper = socket_wrapper
        self.Dispatcher = dispatcher
        self.Timeout = timeout
        
    def __str__(self):
        return "[reader %s]" % (self.Request.Id, )
        
    #def addToBody(self, data):
    #    if PY3:   data = to_bytes(data)
    #    #print ("addToBody:", data)
    #    self.Body.append(data)

    def run(self):
        header = None
        body = b''
        request = self.Request
        csock = request.CSock
        saved_timeout = csock.gettimeout() 
        dispatched = False
        try:
            #self.debug("started")
            self.Started = time.time()
            csock.settimeout(self.Timeout) 
            error = False       
            if self.SocketWrapper is not None:
                try:
                    csock, ssl_info = self.SocketWrapper.wrap(self.Request.CSock)
                    self.Request.CSock = csock
                    self.Request.SSLInfo = ssl_info
                    self.debug("socket wrapped")
                except Exception as e:
                    self.debug("Error wrapping socket: %s" % (e,))
                    error = True
            self.debug("wrapped:", csock)
            if not error:
                header = HTTPHeader()
                request_received, body = header.recv(csock)
                csock.settimeout(saved_timeout) 
    
                if not request_received or not header.is_valid() or not header.is_client():
                    # header not received - end
                    self.debug("request not received or invalid or not client request: %s" % (request,))
                    if header.Error:
                        self.debug("request read error: %s" % (header.Error,))
                    return None
                else:
                    request.HTTPHeader = header
                    request.Body = body
                    app = self.Dispatcher.dispatch(self.Request)
                    dispatched = app is not None
        finally:
            if not dispatched:
                csock.sendall(b"HTTP/1.1 404 Not found\n\n")
                request.close()
            self.SocketWrapper = self.Dispatcher = self.Logger = None

class SSLSocketWrapper(object):
     
    def __init__(self, config, certfile, keyfile, verify, ca_file, password):
        import ssl
        
        keyfile = keyfile or config.get("key")
        certfile = certfile or config.get("cert")
        ca_file = ca_file or config.get("ca_cert")
        verify = verify or config.get("verify", "optional")
        password = password or config.get("password")
        
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
            
    def wrap(self, sock):
        ssl_socket = self.SSLContext.wrap_socket(sock, server_side=True)
        return ssl_socket, ssl_socket

class HTTPServer(PyThread, Logged):

    def __init__(self, port, apps, sock=None, logger=None, max_connections = 100, 
                timeout = 20.0,
                enabled = True, max_queued = 100,
                logging = False, log_file = None, debug=None,
                certfile=None, keyfile=None, verify="none", ca_file=None, password=None
                ):
        PyThread.__init__(self)
        self.Port = port
        self.Sock = sock
        assert self.Port is not None, "Port must be specified"
        if logger is None and logging and log_file is not None:
            f = sys.stdout if log_file == "-" else open(log_file, "a")
            logger = Logger(f)
            #print("logs sent to:", f)
        Logged.__init__(self, f"[server {self.Port}]", logger, debug=True)
        self.Logger = logger
        self.Timeout = timeout
        max_connections =  max_connections
        queue_capacity = max_queued
        self.RequestReaderQueue = TaskQueue(max_connections, capacity=queue_capacity, delegate=self)
        self.SocketWrapper = SocketWrapper(certfile, keyfile, verify, ca_file, password) if keyfile else None
        self.reconfigureApps(apps)
        self.Stop = False
        
    @staticmethod
    def from_config(config, apps, logger=None, logging=False, log_file=None, debug=None):
        port = config["port"]
        
        timeout = config.get("timeout", 20.0)
        max_connections = config.get("max_connections", 100)
        queue_capacity = config.get("queue_capacity", 100)

        # TLS
        certfile = config.get("cert")
        keyfile = config.get("key")
        verify = config.get("verify")
        ca_file = config.get("ca_file")
        password = config.get("password")
        
        return HTTPServer(port, apps, logger=logger, max_connections=max_connections,
                timeout = timeout, max_queued = queue_capacity, 
                logging = logging, log_file=log_file, debug=debug,
                certfile=certfile, keyfile=keyfile, verify=verify, ca_file=ca_file, password=password
        )
        
    @synchronized
    def reconfigureApps(self, apps):
        if isinstance(apps, WPApp):
            apps = [DirectApplication(apps, self.Logger)]
        self.Apps = apps
        
    def connectionCount(self):
        return len(self.Connections)    

    def run(self):
        if self.Sock is None:
            # therwise use the socket supplied to the constructior
            self.Sock = socket(AF_INET, SOCK_STREAM)
            self.Sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.Sock.bind(('', self.Port))
            self.Sock.listen(10)
        while not self.Stop:
            self.debug("--- accept loop port=%d start" % (self.Port,))
            csock = None
            caddr = ('-','-')
            try:
                csock, caddr = self.Sock.accept()
                request = Request(self.Port, csock, caddr)
                self.debug("connection %s accepted from %s:%s" % (request.Id, caddr[0], caddr[1]))
                reader = RequestReader(self, request, self.SocketWrapper, self.Timeout, self.Logger)
                self.RequestReaderQueue << reader
            except Exception as exc:
                #print(exc)
                if not self.Stop:
                    self.debug("connection processing error: %s" % (traceback.format_exc(),))
                    self.log_error(caddr, "Error processing connection: %s" % (exc,))
                    if csock is not None:
                        try:    csock.close()
                        except: pass
                self.debug("--- accept loop port=%d end" % (self.Port,))
        if self.Stop:   self.debug("stopped")
        try:    self.Sock.close()
        except: pass
        self.Sock = None
        
    @synchronized
    def stop(self):
        self.Stop = True
        try:    self.Sock.close()
        except: pass

    @synchronized
    def dispatch(self, request):
        for app in self.Apps:
            if app.accept(request):
                return app
        else:
            return None

    def taskFailed(self, queue, task, exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb)
            
def run_server(port, app, **args):
    assert isinstance(port, int), "Port must be integer"
    assert isinstance(app, WPApp), "Application must be a WPApp"
    srv = HTTPServer(port, app, **args)
    srv.start()
    srv.join()
    

