# function_app.py

from webpie import WPApp

def hello(request, relpath):
    who = relpath or "world"
    return f"Hello, {who}\n"

WPApp(hello).run_server(8080)

