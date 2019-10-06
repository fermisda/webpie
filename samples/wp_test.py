from webpie import WPApp, WPHandler, Response

class SubHandler(WPHandler):
    pass
    
    
class TopHandler(WPHandler):
    
    def __init__(self, *params):
        WPHandler.__init__(self, *params)
        self.A = SubHandler(*params)
        
    def hello(self, request, relpath, **args):
        return "Hello world!\n", "text/plain"
        
    def post(self, request, relpath, **args):
        return "Body length={}".format(len(request.body))
        
    def __call__(self, request, relpath, **args):
        return "Catchall(%s, %s). path=%s\n" % (relpath, args, self.Path)
        
    
WPApp(TopHandler).run_server(8888)

