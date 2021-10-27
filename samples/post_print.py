from webpie import WPApp, WPHandler

class Handler(WPHandler):
    
    def echo(self, request, relpath, **args):
        data = request.body
        return data, 200
        
WPApp(Handler).run_server(8080)