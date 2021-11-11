from webpie import WPApp, WPHandler, HTTPServer, HTTPSServer

class H(WPHandler):
    
    def redirect1(self, request, relpath, to=None):
        return "redirect", 301, {"Location":to}

    def redirect2(self, request, relpath, to=None):
        print("app: request.path_url:", request.path_url)
        self.redirect(to)
        
WPApp(H).run_server(8888)