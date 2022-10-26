from .webob import Response
from .webob.multidict import MultiDict
from .webob import Request as webob_request
from .webob.exc import HTTPTemporaryRedirect, HTTPException, HTTPFound, HTTPForbidden, HTTPNotFound, HTTPBadRequest
from . import Version as WebPieVersion
from urllib.parse import unquote_plus
    
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

class InvalidArgumentError(Exception):
    def __str__(self):
        name, value = self.args
        return f"Invalid argument value: {name}={value}"

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

def _sql_quote_sanitizer(name, value):
    return value.replace("'", "''")

def _check_unsafe_sanitizer(name, value, unsafe="'"):
    #print("_check_unsafe_sanitizer: name=", name, "   value:", value)
    if value and any(c in value for c in unsafe):
        raise InvalidArgumentError(name, value)
    return value

_Sanitizers = {
    "sql":  _sql_quote_sanitizer,
    "safe":  _check_unsafe_sanitizer
}

#
# Decorators
#

def sanitize(sanitizer=None, exclude=[], only=None):
    def decorator(method):
        szr = sanitizer
        onl = only
        excl = exclude
        def decorated(handler, request, relpath, *params, **args):
            "do-not-sanitize"       # signal "already sanitized"
            sanitizer = szr
            only = onl
            exclude = excl
            if isinstance(exclude, str):
                exclude = [exclude]
            if isinstance(only, str):
                only = [only]
            if sanitizer is None:
                sanitizer = handler.App.Sanitizer
            elif sanitizer is False:
                sanitizer = None
            elif isinstance(sanitizer, str):
                sanitizer = handler.App.Sanitizers[sanitizer]
            if sanitizer is not None:
                #print("sanitizing...")
                relpath, args = handler.App.sanitize(sanitizer, request, relpath, args, exclude=exclude, only=only)
                #print("decorated: relpath:", relpath)
            return method(handler, request, relpath, *params, **args)
        return decorated
    return decorator

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

atomic = app_synchronized           # synonym

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

class WPHandler(object):

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

        if isinstance(attr, WPHandler):
            return attr
        elif callable(attr):
            allowed = allowed and not name.startswith('_')
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
        else:
            return None
            
        
    def addHandler(self, name, method):
        self._WebMethods[name] = method

    def _app_lock(self):
        return self.App._app_lock()

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
        
    def canonicPath(self, path):
        return self.App.canonicPath(path)

    def externalPath(self, path):
        return self.App.externalPath(path)

    def destroy(self):
        # override me
        pass

    def initAtPath(self, path):
        # override me
        pass

    def jinja_globals(self):
        # override me
        return {}

    def add_globals(self, data):
        g = {}
        self.App.add_globals(g)
        g.update(self.jinja_globals())
        g.update(data)
        return g

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
        return self.Request.environ.get('SCRIPT_NAME', os.environ.get('SCRIPT_NAME', ''))

    def uriDir(self, ignored=None):
        return os.path.dirname(self.scriptUri())

    def appRootPath(self):
        top = self.App.appRootPath(self.Request.environ)
        if top == "/":  top = ""
        return top
        
    appTopPath = appRootPath            # synonym for backward compatibility

    def externalPath(self, path):
        return self.App.externalPath(path)  # convenience

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
            + ["\nrelpath: %s" % (relpath or "")]
            + ["\nargs:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in args.items()]
            + ["\nrequest.GET:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in req.GET.items()]
            + ["\nrequest.POST:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in req.POST.items()]
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
    Sanitizers = _Sanitizers

    def __init__(self, root_class_or_handler, strict=False, prefix=None, replace_prefix="", 
            environ={}, unquote_args=True, sanitizer=None):

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
        self.Prefix = prefix            # this prefix will be removed from the URL path before the mapping to the method
        self.ReplacePrefix = replace_prefix     # this prefix will be added after self.Prefix was removed
        self.HandlerParams = []
        self.HandlerArgs = {}
        self.Environ = environ
        self.UnquoteArgs = unquote_args

        if isinstance(sanitizer, str):
            sanitizer = self.Sanitizers[sanitizer]
        self.Sanitizer = sanitizer

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

    def canonicPath(self, path):
        # removes all occurances of '//' and '/./'
        # if the path was absoulute, it remains absoulte (starts with '/')
        # makes sure the path does not end with '/' unless it is the root path "/"
        while path and '//' in path:
            path = path.replace('//', '/')
        while path and "/./" in path:
            path = path.replace("/./","/")
        if path and path != '/' and path.endswith('/'):
            path = path[:-1]
        return path

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
            <pre>\n%s</pre>
            </body>
            </html>""" % (headline, exc_text)
        #print exc_text
        return Response(text, status = '500 Application Error')

    def convertPath(self, path):
        if self.Prefix:
            matched = None
            if path == self.Prefix:
                matched = path
            elif path.startswith(self.Prefix + '/'):
                matched = self.Prefix
                
            if matched is None:
                return None

            path = path[len(matched):]

            if self.ReplacePrefix:
                path = self.ReplacePrefix + path
                
            path = self.canonicPath(path or "/")
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
                    if len(words) > 1:  v = unquote_plus(words[1]) if self.UnquoteArgs else words[1]
                    if k in out:
                        old = out[k]
                        if not isinstance(old, list):
                            old = out[k] = [old]
                        old.append(v)
                    else:
                        out[k] = v
        return out

    def sanitize(self, sanitizer, request, relpath, args, exclude=[], only=None):
        if sanitizer is None:
            return relpath, args
        if "(relpath)" not in exclude:  
            relpath = sanitizer('(relpath)', relpath)
        args = {
                name: value if value is None 
                        or name in exclude 
                        or only is not None and name not in only
                else (
                    [sanitizer(name, v) for v in value] 
                    if isinstance(value, list)
                    else sanitizer(name, value)
                ) 
                for name, value in args.items()
        }
        #
        # run sanitizer on GET and POST dictionaries of the request too, even though
        # the values will not be updated. But at least the sanitizer has a chance to raise the UnsafeArgumentError exception
        #
        for name, value in list(request.GET.items()) + list(request.POST.items()):
            if name not in exclude and (only is None or name in olny):
                sanitizer(name, value)
        return relpath, args

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
                if hasattr(method, "__doc__") and "do-not-sanitize" in (method.__doc__ or ""):
                    pass
                elif self.Sanitizer is not None:
                    #print("WPApp.wsgi_call: sanitizing...")
                    relpath, args = self.sanitize(self.Sanitizer, request, relpath, args)
                response = method(request, relpath, **args)  

        except HTTPFound as val:    
            # redirect
            response = val
        except HTTPException as val:
            #print 'caught:', type(val), val
            response = val
        except HTTPResponseException as val:
            #print 'caught:', type(val), val
            response = val
        except InvalidArgumentError as e:
            response = HTTPBadRequest(str(e))
        except Exception as e:
            response = self.applicationErrorResponse(str(e), sys.exc_info())

        try:    
            response = makeResponse(response)
        except ValueError as e:
            response = self.applicationErrorResponse(str(e), sys.exc_info())
        out = response(environ, start_response)
        if isinstance(root_handler, WPHandler):
            root_handler.destroy()
            root_handler._destroy()
        return out

    def scriptUri(self, request_or_environ):
        if isinstance(request_or_environ, Request):
            environ = request_or_environ.environ
        elif isinstance(request_or_environ, dict):
            environ = request_or_environ
        else:
            raise ValueError("expected Request object or the environ dictionary as the first argument. Got "+str(type(request_or_environ)))
        return environ.get('SCRIPT_NAME') or os.environ.get('SCRIPT_NAME', '')

    def externalPath(self, path):
        # converts an absolute URL path to the path to be used by the client to reach the same method
        # path must be absolute
        # essentially trying to reverse all the URL rewriting, which was done to map the URL to the method
        assert path.startswith("/"), f"Can not convert relative path {path} to external path"
        if self.ReplacePrefix and path.startswith(self.ReplacePrefix):
            path = path[len(self.ReplacePrefix):]
        return self.canonicPath(self.ExternalAppRootPath + '/' + path)

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
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
        with self:
            if not self.Initialized:
                self.ScriptName = environ.get('SCRIPT_NAME') or os.environ.get('SCRIPT_NAME', '')
                self.Script = environ.get('SCRIPT_FILENAME') or os.environ.get('UWSGI_SCRIPT_FILENAME')
                self.ScriptHome = os.environ.get('WEBPIE_SCRIPT_HOME') or os.path.dirname(self.Script or sys.argv[0]) or "."
                self.ExternalAppRootPath = self.canonicPath('/' + self.ScriptName + '/' + (self.Prefix or ""))
                self.init()
                self.Initialized = True

        environ["WebPie.version"] = WebPieVersion
        environ["WebPie.path_prefix"] = self.Prefix or ""
        environ["WebPie.path_replace_prefix"] = self.ReplacePrefix or None
        environ["WebPie.app_root_path"] = self.appRootPath()

        root_handler = self.RootHandler or self.RootClass(req, self, *self.HandlerParams, **self.HandlerArgs)
        #print("root_handler:", root_handler)
            
        try:
            out = self.wsgi_call(root_handler, environ, start_response)
            return out
        except:
            resp = self.applicationErrorResponse(
                "Uncaught exception", sys.exc_info())
        return resp(environ, start_response)
        
    def init(self):
        # overraidable. will be called once after self.ScriptName, self.ScriptHome, self.Script are initialized
        # and app.externalPath() is ready to be used
        # it is good idea to init Jinja environment here
        pass
        
    def jinja_globals(self):
        # override me
        return {}

    def add_globals(self, g):
        top = self.appRootPath()
        g.update({ 
            "GLOBAL_AppRootPath":   top,
            "GLOBAL_AppTopPath":    top  # for backward compatibility, deprecated
        })
        g.update(self.JGlobals)
        g.update(self.jinja_globals())
        return g

    def appRootPath(self):
        top = self.ExternalAppRootPath
        if top == "/":  top = ""            # make it possible to concatenate a tail, e.g.:
                                            # appRootPath() + "/static"
        return top
        
    appTopPath = appRootPath            # synonym for backward compatibility, deprecated

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
