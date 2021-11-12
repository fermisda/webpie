# robots.py

from webpie import WPApp, WPHandler, Response

robots_response = """User-agent: *
Disallow: /
"""

class RobotsHandler(WPHandler):
    
    def __call__(self, request, relpath, **args):
        return robots_response, "text/plain"

class MyHandler(WPHandler):             
    
    def __init__(self, *params):
        WPHandler.__init__(self, *params)
        self.addHandler("robots1.txt", RobotsHandler(*params))  # as external handler
        self.addHandler("robots2.txt", self.robots)             # as method
        self.addHandler("robots3.txt", (robots_response, "text/plain"))         # as text
        self.addHandler("robots.txt",                          # as Response object
                Response(robots_response, content_type="text/plain"))
        
    def robots(self, request, relpath, **args):                         
        return robots_response, "text/plain"                          

application = WPApp(MyHandler)
application.run_server(8080)

