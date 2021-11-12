class WHandler(object):
    
    """
    RouteMap = [
        "robots.txt"    :   ("reject", "text/plain"),
        "hello"         :   "Hello world!",
        "subdir/*":     :   SubDir,
        "A"             :   A
    ]
    """
    
    def __init__(self, request, app, path):
        self.Request = request
        self.App = app
        self.Path = path
        
    def walk_down(self, request, path_down):
        
        if not path_down:
            if callable(self):
                return self(request, "", **request["query_dict"])
            else:
                return HTTPNotFound("Invalid path %s" % (request.path_info,))
        
        # Try methods
        method_name = path_down[0]
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            if callable(method):
                allowed = False
                if self._Strict:
                    allowed = (
                            (self._Methods is not None 
                                    and method_name in self._Methods)
                        or
                            (hasattr(method, "__doc__") 
                                    and item.__doc__ == _WebMethodSignature)
                        )
                else:
                    allowed = self._Methods is None or method_name in self._Methods
                if allowed:
                    relpath = "/".join(path_down[1:])
                    return makeResponse(method(request, relpath, **request["query_dict"]))
                else:
                    return HTTPForbidden(request.path_info)
                
        
        # Try route map
        path = "/".join(path_down)
        for pattern, handler in self.RouteMap:
            if fnmatch.fnmatch(pattern, path):
                if isinstance(handler, tuple):
                    return makeResponse(handler)
                elif PY2 and isinstance(handler, (str, unicode)):
                    return makeResponse((handler,))
                elif PY3 and isinstance(handler, str):
                    return makeResponse((handler,))
                elif issubclass(handler, WHandler):
                    child = handler(self.Request, self.App, self.Path + "/" + path_down[0])
                    return child.walk_down(request, path_down[1:])

        # Try callable
        if callable(self):
            return self(self.Request, path, **request["query_dict"])
            
        return HTTPNotFound("Invalid path %s" % (request.path_info,))
                    
        