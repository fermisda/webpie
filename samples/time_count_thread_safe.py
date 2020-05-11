# time_count_thread_safe.py
from webpie import WPApp, WPHandler, atomic
import time

class Handler(WPHandler):                                               

    def time(self, request, relpath):               
        return "[%d]: %s\n" % (self.App.bump_counter(), time.ctime()), "text/plain"

class App(WPApp):

    def __init__(self, handler_class):
        WPApp.__init__(self, handler_class)
        self.Counter = 0
    
    @atomic
    def bump_counter(self):
        self.Counter += 1
        return self.Counter

App(Handler).run_server(8080)

