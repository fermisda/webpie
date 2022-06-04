# http_server.py

from webpie import HTTPServer, WPHandler, WPApp, Logger
import sys, time

class TimeHandler(WPHandler):
    
    def time(self, request, relpath, **args):            # simple "what time is it?" server
        t = time.ctime(time.time())
        return f"""
            <html>
            <head></head>
            <body>
                <p>Time is: {t}</p>
            </body>
            </html>        
        """

app = WPApp(TimeHandler)                        # create app object

port = 8181

logger = Logger("-", debug=True)

srv = HTTPServer(port, app,                    # create HTTP server thread - subclass of threading.Thread
    logging=True, logger=logger,
    max_connections=3, max_queued=5             # concurrency contorl
)     
               
srv.start()                                     # start the server
srv.join()                                      # run forever
