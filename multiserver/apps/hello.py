from webpie import WPApp, WPHandler

class HelloHandler(WPHandler):
    def hello(self, request, relpath, **args):
        return f"Hello from {self.App.MyName}/{relpath}\n"

class HelloApp(WPApp):
    
    def __init__(self, my_name, handler):
        WPApp.__init__(self, handler)
        self.MyName = my_name

def create_application(name):
    return HelloApp(name, HelloHandler)