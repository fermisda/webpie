# function_app.py

from webpie import WPApp

def hello(request, relpath):
    who = relpath or "world"
    return "Hello, "+who, "text/plain"

WPApp(hello).run_server(8080)

