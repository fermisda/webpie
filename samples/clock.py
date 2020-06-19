# clock.py

from webpie import WPApp, WPHandler                       
import time

class Clock(WPHandler):                                

    def time(self, request, relpath):          
        return time.ctime()

app = WPApp(Clock)                             
app.run_server(8081)
