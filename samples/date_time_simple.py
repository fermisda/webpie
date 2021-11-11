# date_time_server.py
from webpie import WPApp, WPHandler
from datetime import datetime, date

class DateTimeHandler(WPHandler):   
    
    def date(self, request, relpath, part=None):
        #
        # will respond to .../date?part=(year|month|day)
        #
        today = date.today()
        if part == "year":
            return str(today.year)+"\n"
        elif part == "month":
            return str(today.month)+"\n"
        elif part == "day":
            return str(today.day)+"\n"
        else:
            return str(today)+"\n"

    def time(self, request, relpath):                              
        #
        # will respond to .../time/(hour|minute|second)
        #
        t = datetime.now()
        if relpath == "hour":
                return str(t.hour)+"\n"
        elif relpath == "minute":
                return str(t.minute)+"\n"
        elif relpath == "second":
                return str(t.second)+"\n"
        else:
                return str(t.time())+"\n"

WPApp(DateTimeHandler).run_server(8080)
