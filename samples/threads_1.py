from webpie import WPApp, WPHandler, atomic

class MyApp(WPApp):
    
    def __init__(self, root_class):
        WPApp.__init__(self, root_class)
        self.Memory = {}
    
class Handler(WPHandler):
    
    @atomic
    def set(self, req, relpath, name=None, value=None, **args):
        self.App.Memory[name]=value
        return "OK\n"
        
    @atomic
    def get(self, req, relpath, name=None, **args):
        return self.App.Memory.get(name, "(undefined)")+"\n"
        
application = MyApp(Handler)
application.run_server(8002)

