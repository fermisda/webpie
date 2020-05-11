# hello_world_wsgi.py

from webpie import WPApp, WPHandler

class MyHandler(WPHandler):                        

    def hello(self, request, relpath):             
        return "Hello, World!\n"                    

application = WPApp(MyHandler)                      # 1
