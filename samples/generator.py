from webpie import WPApp, WPHandler

class H(WPHandler):
    
    def data(self, request, relpath, **agrs):
        out = ("line %d\n" % (i,) for i in range(10))
        return out
        
WPApp(H).run_server(9000)