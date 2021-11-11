from webpie import WPApp
from webpie import WPHandler 
from webpie import run_server
from webpie import Response

class MyApp(WPApp):
    pass
    
class SubHandler(WPHandler):
    
    def index(self, request, relpath, **args):
        return "index"
    
class TopHandler(WPHandler):
    
    def __init__(self, *params):
        WPHandler.__init__(self, *params)
        self.A = SubHandler(request, app, "/A")
        
    def hello(self, request, relpath, **args):
        return "Hello world!", "text/plain"
        
    def post(self, request, relpath, **args):
        return "Data received: {} bytes\n".format(len(request.body))
        
    
app = MyApp(TopHandler)

print("Server is listening at port 8001...")
run_server(8001, app)
