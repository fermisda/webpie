# time_fields.py
from webpie import WPApp, WPHandler
from datetime import datetime

class MyHandler(WPHandler):						

	def time(self, request, relpath):				# 1
		t = datetime.now()
		if not relpath:
			return str(t)+"\n"
		elif relpath == "year":
			return str(t.year)+"\n"
		elif relpath == "month":
			return str(t.month)+"\n"
		elif relpath == "day":
			return str(t.day)+"\n"
		elif relpath == "hour":
			return str(t.hour)+"\n"
		elif relpath == "minute":
			return str(t.minute)+"\n"
		elif relpath == "second":
			return str(t.second)+"\n"

application = WPApp(MyHandler)
application.run_server(8080)
