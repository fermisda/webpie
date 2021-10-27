from webpie import WPApp                                  

def hello(request, relpath, who="world"):                 #1
    my_name = relpath                                     #2
    return f"Hello, {who}! I am {my_name}\n"              #3

WPApp(hello).run_server(8080)                             

