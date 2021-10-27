# hello_time.py
from webpie import WPApp, WPHandler
import time

class MyHandler(WPHandler):                                             

        def hello(self, request, relpath):                              
                return "Hello, World!\n"                                        

        def time(self, request, relpath):                               # 1
                return time.ctime()+"\n", "text/plain"          # 2

WPApp(MyHandler).run_server(8080)
