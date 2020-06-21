Building Threaded Applications
==============================

Each HTTP request is handled by its own Handler object, created from scratch to process this request and this request only and destroyed
when it is done. Each incoming request is parsed into its own WebOb Request object owned by the Handler object. 
The persistent singleton WPApp object is shared by all
the Handlers and can be used for synchronization between them and to keep common data. Depending on the actual HTTP server implementation,
this design allows to build multi-treaded web application. 

WebPie provides some basic tools to build threaded web applications.

WPApp as a Context Manager
--------------------------

If a Handler wants to guard a piece of code as a critical session, so that no other Handler can enter any other
critical section at the same time, the Handler can use the WPApp object as the context manager:

.. code-block:: python

    from webpie import WPApp, WPHandler
    
    class Handler(WPHandler):
    
        def add(self, request, relpath, value=None):
            with self.App:
                # synchronizing on the App makes this code atomic
                self.App.Sum += float(value)
                self.App.Count += 1
                return f"{self.App.Sum/self.App.Count}"
        
        def get(self, request, relpath):
            with self.App:
                # make sure Sum and Count are consistent
                return f"{self.App.Sum/self.App.Count}"
                
    class App(WPApp):
    
        def __init__(self, handler):
            WPApp.__init__(self, handler)
            self.Count = 0
            self.Sum = 0.0
            
    # allow up to 100 threads processing requests concurrently 
    App(Handler).run_server(8080, max_connections=100)      

@app_synchronized Decorator
---------------------------

Another tool to achieve pretty much the same results is to use @app_synchronized decorator:

.. code-block:: python

    from webpie import WPApp, WPHandler
    
    class Handler(WPHandler):
    
        @app_synchronized
        def add(self, request, relpath, value=None):
            # synchronizing on the App makes this code atomic
            self.App.Sum += float(value)
            self.App.Count += 1
            return f"{self.App.Sum/self.App.Count}"
        
        @app_synchronized
        def get(self, request, relpath):
            # make sure Sum and Count are consistent
            return f"{self.App.Sum/self.App.Count}"

    class App(WPApp):
    
        def __init__(self, handler):
            WPApp.__init__(self, handler)
            self.Count = 0
            self.Sum = 0.0
            
    # allow up to 100 threads processing requests concurrently 
    App(Handler).run_server(8080, max_connections=100)      
                

It does pretty much the same thing, but it turns the whole decorated web method into a critical section

@app_synchronized can be applied to Application methods too:

.. code-block:: python

    from webpie import WPApp, WPHandler
    
    class Handler(WPHandler):
    
        def get(self, request, relpath):
            return self.App.get(relpath)

    class App(WPApp):
    
        def __init__(self, handler):
            WPApp.__init__(self, handler)
            self.Cache = {}
        
        @app_synchronized    
        def get(self, path):
            if not path in self.Cache:
                if len(self.Cache) > 100:
                    self.Cache = dict(list(self.Cache.items())[:100])
                self.Cache[path] = open(path, "r").read()
            return self.Cache[path]
            
    # allow up to 100 threads processing requests concurrently 
    App(Handler).run_server(8080, max_connections=100)      
                
Not Enough ?
------------

Because you have full control over the Application and Handler classes, you can build more sophysticated inter-thread synchronization
mechanisms to make your application more efficient.