from webpie import WPApp, WPHandler

class Handler(WPHandler):
    
    def post(self, request, relpath, **args):
        for line in request.body_file.readlines():
            print(line.decode("utf-8").rstrip())
        return "OK"
        
WPApp(Handler).run_server(8080)
