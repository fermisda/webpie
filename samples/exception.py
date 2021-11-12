def iter():
	yield "1\n"
	raise ValueError("error")
	yield "2\n"

def application(request, relpath, **args):
    return iter(), 200

from webpie import WPApp

WPApp(application).run_server(8080)
