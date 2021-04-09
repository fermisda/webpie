# hello_world_wsgi.py

from webpie import WPApp, WPHandler

class Greeter(WPHandler):                        

    def hello(self, request, relpath):             
        return "Hello, World!\n"                    

application = WPApp(Greeter)
