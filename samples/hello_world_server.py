# hello_world_server.py
from webpie import WPApp, WPHandler
import time

class MyHandler(WPHandler):						

	def hello(self, request, relpath):				
		return "Hello, World!\n"					

application = WPApp(MyHandler)
application.run_server(8080)

