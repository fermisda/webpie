# hello_world.py

from webpie import WPApp, WPHandler

class MyHandler(WPHandler):                         # 1

    def hello(self, request, relpath):              # 2
        return "Hello, World!\n"                    # 3

WPApp(MyHandler).run_server(8888)                   # 4
