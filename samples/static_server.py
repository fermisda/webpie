# static_server.py

from webpie import WPApp, WPHandler
import time

class TimeHandler(WPHandler):
    
    def time(self, request, relpath, **args):
        return """
            <html>
            <head>
                <link rel="stylesheet" href="/static/style.css" type="text/css"/>
            </head>
            <body>
                <p class="time">%s</p>
            </body>
            </html>
        """ % (time.ctime(time.time()),)

WPApp(TimeHandler, 
    static_location="./static_content", 
    static_path="/static"
    ).run_server(8080)
