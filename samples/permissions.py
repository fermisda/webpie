# permissions.py
from webpie import WPApp, WPHandler, run_server, webmethod
import time

class H_methods(WPHandler):     

    _Methods = ["hello"]                

    def hello(self, request, relpath):                          
            return "Hello, World!\n"    

    def wrong(self, request, relpath):
        return "This should never happen\n"
        
class H_decorators(WPHandler):

    @webmethod()
    def hello(self, request, relpath):                          
            return "Hello, World!d\n"   

    @webmethod()
    def wrong(self, request, relpath):
        return "This should never happen\n"

class H_permissions(WPHandler):

    def _roles(self, request, relpath):
        return [relpath]

    @webmethod(["read","write"])
    def read_write(self, request, relpath):                             
            return "Read/write access granted\n"        

    @webmethod(["read"])
    def read_only(self, request, relpath):
        return "Read access granted\n"

class H_open(WPHandler):

    def hello(self, request, relpath):                          
            return "Hello, World!\n"    

    def wrong(self, request, relpath):
        return "This should never happen\n"

class Top(WPHandler):

    def __init__(self, *params):
        WPHandler.__init__(self, *params)

        self.o = H_open(req, app, path)
        self.m = H_methods(req, app, path)
        self.d = H_decorators(req, app, path)
        self.p = H_permissions(req, app, path)

application = WPApp(Top, strict=True)
application.run_server(8080)

