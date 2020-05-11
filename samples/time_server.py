# time_server.py
from webpie import WPApp, WPHandler
from datetime import datetime
import time

class TimeHandler(WPHandler):   
    
        def clock(self, request, relpath, format="number"):
            t = time.time()
            if format=="number":
                return str(t)+"\n", "text/plain"
            elif format=="text":
                return time.ctime(t)+"\n", "text/plain"
            elif format == "json":
                return '{"clock":%f}\n' % (t,), "text/json"
            else:
                return "Unknown format %s\n" % (format,), 400

        def time(self, request, relpath):                               # 1
                t = datetime.now()
                if relpath == "year":
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
                else:
                        return str(t)+"\n"

WPApp(TimeHandler).run_server(8080)
