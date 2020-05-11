# time_index.py

from webpie import WPApp, WPHandler
import time

class MyHandler(WPHandler):                                             

        def time(self, request, relpath):
                return time.ctime()+"\n", "text/plain"  

        def index(self, request, relpath):
                return "[index] "+time.ctime()+"\n", "text/plain" 

WPApp(MyHandler).run_server(8080)
