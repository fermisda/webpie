# callable_handler.py

from webpie import WPApp, WPHandler
import json

class MyApp(WPApp):

    def __init__(self, root_class):
        WPApp.__init__(self, root_class)
        self.Memory = {}

class Handler(WPHandler):
    
    def keys(self, request, relpath):
        return json.dumps(sorted(list(self.App.Memory.keys())))+"\n", "text/json"
    
    def __call__(self, request, relpath):   # 
        var_name = relpath
        method = request.method             # request is a WebOb Request object
        if method.upper() == "GET":
            value = self.App.Memory.get(var_name)
        else:
            value = json.loads(request.body)
            self.App.Memory[var_name] = value
        return json.dumps(value)+"\n", "text/json"
            
MyApp(Handler).run_server(8080)
