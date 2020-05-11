# lambda_app.py

from webpie import WPApp

WPApp(lambda request, relpath: ("Hello, %s\n" % (relpath or "world",), "text/plain")).run_server(8080)
