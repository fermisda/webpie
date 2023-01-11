# time_app.py
from webpie import WPApp, WPHandler
import time
from random import random as rnd

class MyHandler(WPHandler):                                             

    def hello(self, request, relpath, delay=0, random="no"):
        delay = float(delay)
        if random == "yes":
            delay = delay * rnd()
        time.sleep(delay)
        return "hello\n"

if __name__ == "__main__":
    WPApp(MyHandler).run_server(8080)
else:
    application = WPApp(MyHandler)


