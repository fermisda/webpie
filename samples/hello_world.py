# hello_world.py

from webpie import WPApp, WPHandler

class MyHandler(WPHandler):                         # 1

    def hello(self, request, relpath):              # 2
        return "Hello, World!\n"                    # 3

import sys

port = 8080
if sys.argv[1:]:
    port = int(sys.argv[1])
print("Starting on port", port)
WPApp(MyHandler).run_server(port)                   # 4
