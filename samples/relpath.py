# relpath.py

from webpie import WPApp, WPHandler

class MyHandler(WPHandler):                         

    def hello(self, request, relpath):              
        return "Hello %s!\n" % (relpath,)            # 1

WPApp(MyHandler).run_server(8080)                    
