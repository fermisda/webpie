# time_args.py
from webpie import WPApp, WPHandler
from datetime import datetime

class MyHandler(WPHandler):                                             

        def time(self, request, relpath, field="all"):          
                t = datetime.now()
                if field == "all":
                        return str(t)+"\n"
                elif field == "year":
                        return str(t.year)+"\n"
                elif field == "month":
                        return str(t.month)+"\n"
                elif field == "day":
                        return str(t.day)+"\n"
                elif field == "hour":
                        return str(t.hour)+"\n"
                elif field == "minute":
                        return str(t.minute)+"\n"
                elif field == "second":
                        return str(t.second)+"\n"

WPApp(MyHandler).run_server(8080)
