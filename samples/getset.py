# getset.py

from webpie import WPApp, WPHandler

class MyApp(WPApp):

    def __init__(self, root_class):
        WPApp.__init__(self, root_class)
        self.Memory = {}

class Handler(WPHandler):

    def set(self, req, relpath, name=None, value=None, **args):
        with self.App:
            self.App.Memory[name]=value
        return "OK\n"
    
    def get(self, req, relpath, name=None, **args):
        with self.App:
            return self.App.Memory.get(name, "(undefined)") + "\n"
    
MyApp(Handler).run_server(8080)
