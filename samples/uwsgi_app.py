from webpie import WPApp, WPHandler, run_server, Response

class MyApp(WPApp):
    pass
    
class SubHandler(WPHandler):
    pass
    
class TopHandler(WPHandler):
    
    def __init__(self, *params):
        WPHandler.__init__(self, *params)
        self.A = SubHandler(request, app, "/A")
        
    def hello(self, request, relpath, **args):
        return "Hello world!\n", "text/plain"
        
    def post(self, request, relpath, **args):
        return "Body length={}".format(len(request.body))
        
    
application = MyApp(TopHandler)

