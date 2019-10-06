from webpie import WPApp
from webpie import WPHandler, WebPieStaticHandler
from webpie import run_server
from webpie import Response

class MyApp(WPApp):
    pass
    
class TopHandler(WPHandler):
    
    def hello(self, request, relpath, **args):
        return "Hello world!", "text/plain"
        
app = MyApp(TopHandler, static_location="static", static_path="/s")

print("Server is listening at port 8001...")
run_server(8001, app)
