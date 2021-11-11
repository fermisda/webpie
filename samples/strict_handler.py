# strict_handler.py

from webpie import WPApp, WPHandler

class StrictHandler(WPHandler):                     
    
    _Methods = ["hello"]                                # 1

    def password(self, realm, user):                    # 2
        return "H3llo-W0rld"

    def hello(self, request, relpath):                  
        try:    user, password = relpath.split("/",1)
        except: return 400                              # 3
        if password == self.password("realm", user):
            return "Hello, World!\n"                    
        else:
            return "Unauthorized\n", 401

WPApp(StrictHandler).run_server(8080)                   
