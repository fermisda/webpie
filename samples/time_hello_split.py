# time_hello_split.py
from webpie import WPApp, WPHandler
import time

class Greeter(WPHandler):                                               

        def hello(self, request, relpath):                              
                return "Hello, World!\n"                                        

class Clock(WPHandler):                                         

        def time(self, request, relpath):                               # 1
                return time.ctime()+"\n", "text/plain"          # 2

class TopHandler(WPHandler):

        def __init__(self, *params):
                WPHandler.__init__(self, *params)
                self.greet = Greeter(*params)
                self.clock = Clock(*params)

        def version(self, request, relpath):
                return "1.0.2"


application = WPApp(TopHandler)
application.run_server(8080)
