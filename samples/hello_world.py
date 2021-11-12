# hello_world.py

from webpie import WPApp

def hello(request, relpath):
    return f"Hello, World!\n"

WPApp(hello).run_server(9000)

