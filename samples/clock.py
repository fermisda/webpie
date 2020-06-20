# clock.py

from webpie import WPApp, WPHandler                       
import time

class Clock(WPHandler):                                

    def ctime(self, request, relpath):          
        return "%s\n" % time.ctime()

    def clock(self, request, relpath):          
        return "%f\n" % time.time()

WPApp(Clock).run_server(8080)
