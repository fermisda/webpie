# static_server.py

from webpie import WPApp, WPHandler, WPStaticHandler
import time

class Static(WPHandler):
    
    def __init__(self, request, app):
        WPHandler.__init__(self, request, app)
        self.static = WPStaticHandler(request, app, "./static_content",
            cache_ttl=300)
    
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

WPApp(Static).run_server(8080)
