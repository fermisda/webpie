from webpie import WPApp

def echo(request, relpath):
    return relpath or "", "text/plain"

application = WPApp(echo)