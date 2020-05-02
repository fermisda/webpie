from webpie import WPApp

def hello(request, relpath, **args):
    return "hello there, "+relpath

WPApp(hello).run_server(8080)
