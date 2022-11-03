# hello_world.py

from webpie import WPApp, WPHandler

class Handler(WPHandler):

    def hello(self, request, relpath, **args):
        return f"Hello, World ({relpath})\n"

WPApp(Handler).run_server(9000)

