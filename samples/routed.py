from webpie import WPApp, WPHandler

def robots(request, relpath, **args):
        return "reject"

class MyHandler(WPHandler):
    def __init__(self, *params):
        WPHandler.__init__(self, *params)
        self.addHandler("robots.txt", "reject", 400)

WPApp(MyHandler).run_server(8080)
