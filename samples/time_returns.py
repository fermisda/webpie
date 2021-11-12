# time_returns.py

from webpie import WPApp, WPHandler, Response
import time, json

class MyHandler(WPHandler):                                             

    def hello(self, request, relpath):                          
        return "Hello, World!\n"                                        

    def time(self, request, relpath):                           
        return time.ctime()+"\n", "text/plain"          
    
    def time_response(self, request, relpath):
        return Response(time.ctime()+"\n", content_type="text/plain")
        
    def time_generator(self, request, relpath, n=5):
        n = int(n)
        return (time.sleep(1.0) or "{}: {}\n".format(i, time.ctime()) for i in range(n))
        
    def time_headers(self, request, relpath):
        return "OK", {
                "X-Time":       time.ctime(), 
                "X-Clock":      str(time.time()),
                "Content-type": "text/plain"
        }
        
    def time_json(self, request, relpath, **extra):
        data = {}
        data.update(extra)
        data.update(
            {
                "ctime":    time.ctime(),
                "clock":    time.time()
            }
        )
        return json.dumps(data), "text/json"
        
WPApp(MyHandler).run_server(8080)
