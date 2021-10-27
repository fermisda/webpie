# nested_handlers.py

from webpie import WPApp, WPHandler
import time

class HelloHandler(WPHandler):                      #1 

    def hello(self, request, relpath):                              
        return "Hello, World!\n"                                        

class ClockHandler(WPHandler):                      #2 

    def time(self, request, relpath):                       
        return time.ctime()+"\n", "text/plain"      #3

class TopHandler(WPHandler):

    def __init__(self, *params):                    #4
        WPHandler.__init__(self, *params)
        self.greet = HelloHandler(*params)
        self.clock = ClockHandler(*params)

    def version(self, request, relpath):            #5
        return "1.0.3"

WPApp(TopHandler).run_server(8080)
