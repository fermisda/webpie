# hello_world_relpath.py

from webpie import WPApp, WPHandler

class MyHandler(WPHandler):                         # 1

    def hello(self, request, relpath):              # 2
        who = relpath or "World"
        return f"Hello, {who}!\n"                    # 3

WPApp(MyHandler).run_server(8080)

