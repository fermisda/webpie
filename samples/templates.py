# templates.py
from webpie import WPApp, WPHandler
import time

Version = "1.3"

def format_time(t):
    return time.ctime(t)

class MyHandler(WPHandler):                                             

    def time(self, request, relpath):
        return self.render_to_response("time.html", t=time.time())
        
application = WPApp(MyHandler)
application.initJinjaEnvironment(
    ["samples"], 
    filters={ "format": format_time },
    globals={ "version": Version }
    )
application.run_server(8080)
