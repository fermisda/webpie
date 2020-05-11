from webpie import WPApp, WPHandler
import time

class MyHandler(WPHandler):                                             

    def __call__(self, request, relpath, **args):
        return "__call__(%s, %s)" % (relpath, args)

    def hello_str(self, request, relpath):                              
        return "Hello, World!\n"        
    
    def hello_bytes(self, request, relpath):                            
        return b"Hello, World!\n"       
    
    def it_str(self, request, relpath):
        return ("%d = %d\n" % (x, x**2) for x in range(10))                             

    def it_bytes(self, request, relpath):
        return (b"%d = %d\n" % (x, x**2) for x in range(10))                            

    def list_bytes(self, request, relpath):
        return [b"%d = %d\n" % (x, x**2) for x in range(10)]                    

WPApp(MyHandler, prefix="/a/b", replace_prefix="/x").run_server(8080)

