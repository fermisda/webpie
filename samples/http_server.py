# http_server.py

from webpie import HTTPServer, WPHandler, WPApp
import sys, time

class TimeHandler(WPHandler):
    
    def time(self, relpath, **args):            # simple "what time is it?" server
        return time.ctime(time.time())

app = WPApp(TimeHandler)                        # create app object

port = 8080

srv = HTTPSServer(port, app,                    # create HTTP server thread - subclass of threading.Thread
    max_connections=3, max_queued=5             # concurrency contorl
)     
               
srv.start()                                     # start the server
srv.join()                                      # run forever
