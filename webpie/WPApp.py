from .webob import Response
from .webob import Request as webob_request
from .webob.exc import HTTPTemporaryRedirect, HTTPException, HTTPFound, HTTPForbidden, HTTPNotFound
    
import os.path, os, stat, sys, traceback, fnmatch, datetime, inspect, json
from threading import RLock

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    def to_bytes(s):    
        return s if isinstance(s, bytes) else s.encode("utf-8")
    def to_str(b):    
        return b if isinstance(b, str) else b.decode("utf-8", "ignore")
else:
    def to_bytes(s):    
        return bytes(s)
    def to_str(b):    
        return str(b)
    

try:
    from collections.abc import Iterable    # Python3
except ImportError:
    from collections import Iterable

_WebMethodSignature = "__WebPie:webmethod__"

_MIME_TYPES_BASE = {
        "gif":   "image/gif",
        "png":   "image/png",
        "jpg":   "image/jpeg",
        "jpeg":   "image/jpeg",
        "js":   "text/javascript",
        "html":   "text/html",
        "txt":   "text/plain",
        "csv":   "text/csv",
        "json":   "text/json",
        "css":  "text/css"
    }

#
# Decorators
#
 
def webmethod(permissions=None):
    #
    # Usage:
    #
    # class Handler(WebPieHandler):
    #   ...
    #   @webmethod()            # <-- important: parenthesis required !
    #   def hello(self, req, relpath, **args):
    #       ...
    #
    #   @webmethod(permissions=["admin"])
    #   def method(self, req, relpath, **args):
    #       ...
    #
    def decorator(method):
        def decorated(handler, request, relpath, *params, **args):
            #if isinstance(permissions, str):
            #    permissions = [permissions]
            if permissions is not None:
                try:    roles = handler._roles(request, relpath)
                except:
                    return HTTPForbidden("Not authorized\n")
                if isinstance(roles, str):
                    roles = [roles]
                for r in roles:
                    if r in permissions:
                        break
                else:
                    return HTTPForbidden()
            return method(handler, request, relpath, *params, **args)
        decorated.__doc__ = _WebMethodSignature
        return decorated
    return decorator

def app_synchronized(method):
    def synchronized_method(self, *params, **args):
        with self._app_lock():
            return method(self, *params, **args)
    return synchronized_method

atomic = app_synchronized

class Request(webob_request):
    def __init__(self, *agrs, **kv):
        webob_request.__init__(self, *agrs, **kv)
        self.args = self.environ['QUERY_STRING']
        self._response = Response()
        
    def write(self, txt):
        self._response.write(txt)
        
    def getResponse(self):
        return self._response
        
    def set_response_content_type(self, t):
        self._response.content_type = t
        
    def get_response_content_type(self):
        return self._response.content_type
        
    def del_response_content_type(self):
        pass
        
    response_content_type = property(get_response_content_type, 
        set_response_content_type,
        del_response_content_type, 
        "Response content type")

class HTTPResponseException(Exception):
    def __init__(self, response):
        self.value = response

def makeResponse(resp):
    #
    # acceptable responses:
    #
    # Response
    # text              -- ala Flask
    # status    
    # dictionary -> JSON representation, content_type = "text/json"
    # (text, status)            
    # (text, "content_type")            
    # (text, {headers})            
    # (text, status, "content_type")
    # (text, status, {headers})
    # ...
    #
    

    if isinstance(resp, Response):
        return resp
    elif isinstance(resp, int):
        return Response(status=resp)
    
    app_iter = None
    text = None
    content_type = None
    status = None
    headers = None
    
    if not isinstance(resp, tuple):
        resp = (resp,)

    for part in resp:
        
        if app_iter is None and text is None:
            if isinstance(part, dict):
                app_iter = [json.dumps(part).encode("utf-8")]
                content_type = "text/json"
                continue
            elif PY2 and isinstance(part, (str, bytes, unicode)):
                app_iter = [part]
                continue
            elif PY3 and isinstance(part, bytes):
                app_iter = [part]
                continue
            elif PY3 and isinstance(part, str):
                text = part
                continue
            elif isinstance(part, list):
                app_iter = [to_bytes(x) for x in part]
                continue            
            elif isinstance(part, Iterable):
                app_iter = (to_bytes(x) for x in part)
                continue            
        
        if isinstance(part, dict):
            headers = part
        elif isinstance(part, int):
            status = part
        elif isinstance(part, str):
            content_type = part
        else:
            raise ValueError("Can not convert to a Response: " + repr(resp))
            
    #print("resp:", resp, " -->", "  app_iter:", app_iter,"  content_type:", content_type)
            
    response = Response(app_iter=app_iter, status=status)
    if headers is not None: 
        #print("setting headers:", headers)
        response.headers = headers
    if content_type:
        response.content_type = content_type    # make sure to apply this after headers
    if text is not None:  response.text = text
    #print(response)
    return response

class WPHandler:

    Version = ""
    
    _Strict = False
    _MethodNames = None
    
    DefaultMethod = "index"
    
    def __init__(self, request, app):
        self.Request = request
        self.Path = None
        self.App = app
        self.BeingDestroyed = False
        try:    self.AppURL = request.application_url
        except: self.AppURL = None
        #self.RouteMap = []
        self._WebMethods = {}
        if not self._Strict:
            self.addHandler(".env", self._env__)
            
    def step_down(self, name):
        if not name:    return self
        allowed = not self._Strict
        attr = None
        if hasattr(self, name):
            attr = getattr(self, name)
        elif name in self._WebMethods:
            attr = self._WebMethods[name]
            allowed = True
            
        if attr is None:
            return None
            
        if callable(attr):
            allowed = allowed or (
                        (self._MethodNames is not None 
                                and name in self._MethodNames)
                    or
                        (hasattr(method, "__doc__") 
                                and method.__doc__ == _WebMethodSignature)
                    )
            if not allowed:
                return None
            return attr
        elif isinstance(attr, WPHandler):
            return attr
        else:
            return None
            
        
    def addHandler(self, name, method):
        self._WebMethods[name] = method

    def _app_lock(self):
        return self.App._app_lock()

    def initAtPath(self, path):
        # override me
        pass

    def _checkPermissions(self, x):
        #self.apacheLog("doc: %s" % (x.__doc__,))
        try:    docstr = x.__doc__
        except: docstr = None
        if docstr and docstr[:10] == '__roles__:':
            roles = [x.strip() for x in docstr[10:].strip().split(',')]
            #self.apacheLog("roles: %s" % (roles,))
            return self.checkRoles(roles)
        return True
        
    def checkRoles(self, roles):
        # override me
        return True

    def _destroy(self):
        self.App = None
        if self.BeingDestroyed: return      # avoid infinite loops
        self.BeingDestroyed = True
        for k in self.__dict__:
            o = self.__dict__[k]
            if isinstance(o, WPHandler):
                try:    o.destroy()
                except: pass
                o._destroy()
        self.BeingDestroyed = False
        
    def destroy(self):
        # override me
        pass

    def initAtPath(self, path):
        # override me
        pass

    def jinja_globals(self):
        # override me
        return {}

    def add_globals(self, d):
        params = {  
            'APP_URL':  self.AppURL,
            'MY_PATH':  self.Path,
            "GLOBAL_AppTopPath":    self.scriptUri(),
            "GLOBAL_AppDirPath":    self.uriDir(),
            "GLOBAL_ImagesPath":    self.uriDir()+"/images",
            "GLOBAL_AppVersion":    self.App.Version,
            "GLOBAL_AppObject":     self.App
            }
        params = self.App.add_globals(params)
        params.update(self.jinja_globals())
        params.update(d)
        return params

    def render_to_string(self, temp, **args):
        params = self.add_globals(args)
        return self.App.render_to_string(temp, **params)

    def render_to_iterator(self, temp, **args):
        params = self.add_globals(args)
        #print 'render_to_iterator:', params
        return self.App.render_to_iterator(temp, **params)

    def render_to_response(self, temp, **more_args):
        return Response(self.render_to_string(temp, **more_args))

    def mergeLines(self, iter, n=50):
        buf = []
        for l in iter:
            if len(buf) >= n:
                yield ''.join(buf)
                buf = []
            buf.append(l)
        if buf:
            yield ''.join(buf)

    def render_to_response_iterator(self, temp, _merge_lines=0,
                    **more_args):
        it = self.render_to_iterator(temp, **more_args)
        #print it
        if _merge_lines > 1:
            merged = self.mergeLines(it, _merge_lines)
        else:
            merged = it
        return Response(app_iter = merged)

    def redirect(self, location):
        #print 'redirect to: ', location
        #raise HTTPTemporaryRedirect(location=location)
        raise HTTPFound(location=location)
        
    def getSessionData(self):
        return self.App.getSessionData()
        
        
    def scriptUri(self, ignored=None):
        return self.Request.environ.get('SCRIPT_NAME',
                os.environ.get('SCRIPT_NAME', '')
        )
        
    def uriDir(self, ignored=None):
        return os.path.dirname(self.scriptUri())
        
    def renderTemplate(self, ignored, template, _dict = {}, **args):
        # backward compatibility method
        params = {}
        params.update(_dict)
        params.update(args)
        raise HTTPException("200 OK", self.render_to_response(template, **params))

    @property
    def session(self):
        return self.Request.environ["webpie.session"]
        
    #
    # This web methods can be used for debugging
    # call it as "../.env"
    #

    def _env__(self, req, relpath, **args):
        lines = (
            ["request.environ:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in sorted(req.environ.items())]
            + ["relpath: %s" % (relpath or "")]
            + ["args:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in args.items()]
        )
        return "\n".join(lines) + "\n", "text/plain"
        
class WPStaticHandler(WPHandler):
    
    def __init__(self, request, app, root="static", default_file="index.html", cache_ttl=None):
        WPHandler.__init__(self, request, app)
        self.DefaultFile = default_file
        if not (root.startswith(".") or root.startswith("/")):
            root = self.App.ScriptHome + "/" + root
        self.Root = root
        self.CacheTTL = cache_ttl

    def __call__(self, request, relpath, **args):
        
        if ".." in relpath:
            return Response("Forbidden", status=403)

        if relpath == "index":
            self.redirect("./index.html")
            
        home = self.Root
        path = os.path.join(home, relpath)
        
        if not os.path.exists(path):
            return Response("Not found", status=404)

        if os.path.isdir(path) and self.DefaultFile:
            path = os.path.join(path, self.DefaultFile)
            
        if not os.path.isfile(path):
            #print "not a regular file"
            return Response("Not found", status=404)
            
        mtime = os.path.getmtime(path)
        mtime = datetime.datetime.utcfromtimestamp(mtime)
        
        if "If-Modified-Since" in request.headers:
            # <day-name>, <day> <month> <year> <hour>:<minute>:<second> GMT
            dt_str = request.headers["If-Modified-Since"]
            words = dt_str.split()
            if len(words) == 6 and words[-1] == "GMT":
                dt_str = " ".join(words[1:-1])      # keep only <day> <month> <year> <hour>:<minute>:<second>
                dt = datetime.datetime.strptime(dt_str, '%d %b %Y %H:%M:%S')
                if mtime < dt:
                    return 304
            
        size = os.path.getsize(path)

        ext = path.rsplit('.',1)[-1]
        mime_type = _MIME_TYPES_BASE.get(ext, "text/plain")

        def read_iter(f):
            while True:
                data = f.read(8192)
                if not data:    break
                yield data

        resp = Response(app_iter = read_iter(open(path, "rb")), content_length=size, content_type = mime_type)
        #resp.headers["Last-Modified"] = mtime.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if self.CacheTTL is not None:
            resp.cache_control.max_age = self.CacheTTL        
        return resp

class WPApp(object):

    Version = "Undefined"

    def __init__(self, root_class_or_handler, strict=False, 
            static_path="/static", static_location=None, enable_static=False,
            prefix=None, replace_prefix="",
            environ={}):

        self.RootHandler = self.RootClass = None
        if inspect.isclass(root_class_or_handler):
            self.RootClass = root_class_or_handler
        else:
            self.RootHandler = root_class_or_handler
        #print("WPApp.__init__: self.RootClass=", self.RootClass, "   self.RootHandler=", self.RootHandler)
        self.JEnv = None
        self._AppLock = RLock()
        self.ScriptHome = None
        self.Initialized = False
        self.Prefix = prefix
        self.ReplacePrefix = replace_prefix
        self.HandlerParams = []
        self.HandlerArgs = {}
        self.Environ = {}
        self.Environ.update(environ)
        
    def _app_lock(self):
        return self._AppLock
        
    def __enter__(self):
        return self._AppLock.__enter__()
        
    def __exit__(self, *params):
        return self._AppLock.__exit__(*params)
    
    # override
    @app_synchronized
    def acceptIncomingTransfer(self, method, uri, headers):
        return True

    def init(self):
        pass

    @app_synchronized
    def initJinjaEnvironment(self, tempdirs = [], filters = {}, globals = {}):
        # to be called by subclass
        #print "initJinja2(%s)" % (tempdirs,)
        from jinja2 import Environment, FileSystemLoader
        if not isinstance(tempdirs, list):
            tempdirs = [tempdirs]
        self.JEnv = Environment(
            loader=FileSystemLoader(tempdirs)
            )
        for n, f in filters.items():
            self.JEnv.filters[n] = f
        self.JGlobals = {}
        self.JGlobals.update(globals)
                
    @app_synchronized
    def setJinjaFilters(self, filters):
        for n, f in filters.items():
            self.JEnv.filters[n] = f

    def setJinjaGlobals(self, globals):
        self.JGlobals = globals.copy()

    def applicationErrorResponse(self, headline, exc_info):
        typ, val, tb = exc_info
        exc_text = traceback.format_exception(typ, val, tb)
        exc_text = ''.join(exc_text)
        text = """<html><body><h2>Application error</h2>
            <h3>%s</h3>
            <pre>%s</pre>
            </body>
            </html>""" % (headline, exc_text)
        #print exc_text
        return Response(text, status = '500 Application Error')

    def convertPath(self, path):
        if self.Prefix is not None:
            matched = None
            if path == self.Prefix:
                matched = path
            elif path.startswith(self.Prefix + '/'):
                matched = self.Prefix
                
            if matched is None:
                return None
                
            if self.ReplacePrefix is not None:
                path = self.ReplacePrefix + path[len(matched):]
                
            path = path or "/"
            #print(f"converted to: [{path}]")
                
        return path
                
    def handler_options(self, *params, **args):
        self.HandlerParams = params
        self.HandlerArgs = args
        return self

    def find_web_method(self, handler, request, path, path_down, args):
        #
        # walks down the tree of handler finds the web method and calls it
        # returs the Response
        #
        
        
        path = path or "/"
        method = None
        while path_down and not path_down[0]:
            path_down.pop(0)
            
        #is_wp_handler = isinstance(handler, WPHandler)
        #print(f"find_web_method({handler}, WPHandler:{is_wp_handler}, path={path}, path_down={path_down})")

        if isinstance(handler, WPHandler):  
            handler.Path = path
            
            if path_down:
                name = path_down[0]
                attr = handler.step_down(name)
                if attr is not None:
                    if not path.endswith("/"):  path += "/"
                    return self.find_web_method(attr, request, path + name, path_down[1:], args)
                    
            if callable(handler):
                method = handler
            elif not path_down:
                prefix = (path.split("/")[-1] or ".") + "/"
                redirect = prefix + handler.DefaultMethod
                raise HTTPFound(location=redirect)
        elif callable(handler):
            method = handler
            
        relpath = "/".join(path_down)
        return method, relpath

    def parseQuery(self, query):
        out = {}
        for w in (query or "").split("&"):
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
        
    def wsgi_call(self, root_handler, environ, start_response):
        # path_to = '/'
        path = environ.get('PATH_INFO', '')
        #while "//" in path:
        #    path.replace("//", "/")
        path_down = path.split("/")
        #while '' in path_down:
        #    path_down.remove('')
        args = self.parseQuery(environ.get("QUERY_STRING", ""))
        request = Request(environ)
        try:
            method, relpath = self.find_web_method(root_handler, request, "", path_down, args)
            #print("WPApp.wsgi_call: method:", method, "   relpath:", relpath)
            if method is None:
                response = HTTPNotFound("Invalid path %s" % (path,))
            else:
                #print("method:", method)
                response = method(request, relpath, **args)  
                #print("response:", response)                  
            
        except HTTPFound as val:    
            # redirect
            response = val
        except HTTPException as val:
            #print 'caught:', type(val), val
            response = val
        except HTTPResponseException as val:
            #print 'caught:', type(val), val
            response = val
        except:
            response = self.applicationErrorResponse("Uncaught exception", sys.exc_info())

        try:    
            response = makeResponse(response)
        except ValueError as e:
            response = self.applicationErrorResponse(str(e), sys.exc_info())
        out = response(environ, start_response)
        if isinstance(root_handler, WPHandler):
            root_handler.destroy()
            root_handler._destroy()
        return out

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        #print('app call: path:', path)
        if not "WebPie.original_path" in environ:
            environ["WebPie.original_path"] = path
        environ.update(self.Environ)
        #print 'path:', path_down


        path = self.convertPath(path)
        if path is None:
            return HTTPNotFound()(environ, start_response)
        
        #if (not path or path=="/") and self.DefaultPath is not None:
        #    #print ("redirecting to", self.DefaultPath)
        #    return HTTPFound(location=self.DefaultPath)(environ, start_response)
            
        environ["PATH_INFO"] = path

        req = Request(environ)
        if not self.Initialized:
            self.ScriptName = environ.get('SCRIPT_NAME') or ''
            self.Script = environ.get('SCRIPT_FILENAME') or \
                        os.environ.get('UWSGI_SCRIPT_FILENAME')
            self.ScriptHome = os.path.dirname(self.Script or sys.argv[0]) or "."
            self.init()
            self.Initialized = True

            self.init()

        root_handler = self.RootHandler or self.RootClass(req, self, *self.HandlerParams, **self.HandlerArgs)
        #print("root_handler:", root_handler)
            
        try:
            return self.wsgi_call(root_handler, environ, start_response)
        except:
            resp = self.applicationErrorResponse(
                "Uncaught exception", sys.exc_info())
        return resp(environ, start_response)
        
    def init(self):
        # overraidable. will be called once after self.ScriptName, self.ScriptHome, self.Script are initialized
        # it is good idea to init Jinja environment here
        pass
        
    def jinja_globals(self):
        # override me
        return {}

    def add_globals(self, d):
        params = {}
        params.update(self.JGlobals)
        params.update(self.jinja_globals())
        params.update(d)
        return params
        
    def render_to_string(self, temp, **kv):
        t = self.JEnv.get_template(temp)
        return t.render(self.add_globals(kv))

    def render_to_iterator(self, temp, **kv):
        t = self.JEnv.get_template(temp)
        return t.generate(self.add_globals(kv))

    def run_server(self, port, **args):
        from .HTTPServer import HTTPServer
        srv = HTTPServer(port, self, **args)
        srv.start()
        srv.join()

class LambdaHandler(WPHandler):
    
    def __init__(self, func, request, app):
        WPHandler.__init__(self, request, app)
        self.F = func
        
    def __call__(self, request, relpath, **args):
        out = self.F(request, relpath, **args)
        return out
        
class LambdaHandlerFactory(object):
    
    def __init__(self, func):
        self.Func = func
        
    def __call__(self, request, app):
        return LambdaHandler(self.Func, request, app)
        
if __name__ == '__main__':
    from HTTPServer import HTTPServer
    
    class MyApp(WPApp):
        pass
        
    class MyHandler(WPHandler):
        pass
            
    MyApp(MyHandler).run_server(8080)
