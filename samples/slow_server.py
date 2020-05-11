# time_app.py
from webpie import WPApp, WPHandler
import time

class MyHandler(WPHandler):                                             

    def lines(self, request, relpath, lines=10, line_delay=1):
        return (time.sleep(line_delay) or "line {}\n".format(i,) for i in range(int(lines)))

    def data(self, request, relpath, size=1000000, delay=0.0, **args):
        delay = float(delay)
        time.sleep(delay)
        data = '-'*size
        return data

application = WPApp(MyHandler)
application.run_server(8080)


