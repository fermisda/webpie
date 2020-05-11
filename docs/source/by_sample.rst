WebPie by sample
================

This document demonstrates various features of WebPie using short code samples.


Hello World
-----------

Here is almost the simplest WebPie application you can write. In fact it can be even shorter, but we will
keep that for later.

.. code-block:: python

    # hello_world.py

    from webpie import WPApp, WPHandler		
	
    class MyHandler(WPHandler):                         # 1

        def hello(self, request, relpath):              # 2
            return "Hello, World!\n"                    # 3
		
    WPApp(MyHandler).run_server(8080)                   # 4


#1: We created class MyHandler, which will handle HTTP requests. In order to work with WebPie, it has to be a subclass of WPHandler class.

#2: We defined one web method "hello", which will be called when a URL like http://host.org/hello is requested.

#3: It will always return text "Hello, World!".

#4: Finally, we create WebPie Application object and run it as an HTTP server listening on port 8080.

Now we can test it:

.. code-block:: bash

    $ python hello_world.py &
    $ curl http://localhost:8080/hello
    Hello world!
    $ 

relpath
-------

relpath is used by WebPie to pass the rest of the URI path after the head of the URI was mapped to a web method

.. code-block:: python

    # relpath.py

    from webpie import WPApp, WPHandler

    class MyHandler(WPHandler):                         

        def hello(self, request, relpath):              
            return "Hello %s!\n" % (relpath,)            # 1

    WPApp(MyHandler).run_server(8080)                    

#1: copy the rest of the URI to the response

.. code-block:: bash

    $ python hello_world.py &
    $ curl http://localhost:8080/hello/there
    Hello there!
    $ curl http://localhost:8080/hello/wonderful/world/of/web/pie
    Hello wonderful/world/of/web/pie!
    $
    
uWSGI
-----

WebPie Application (WPApp) object can work as a callable WSGI function and therefore can be plugged into any
web server framework which accepts WSGI functions. For example, here is how to run our "Hello World!" 
server under uWSGI:

.. code-block:: python

    # hello_world_wsgi.py

    from webpie import WPApp, WPHandler

    class MyHandler(WPHandler):                        

        def hello(self, request, relpath):             
            return "Hello, World!\n"                    

    application = WPApp(MyHandler)                      # 1

        
#1: WebPie application object is callable as WSGI-compliant function

.. code-block:: bash

	$ uwsgi --http :8080 --wsgi-file hello_world_wsgi.py


and try it:

.. code-block:: bash

	$ curl http://localhost:8080/hello
	Hello world!
	$ 

URL Structure
-------------
Notice that MyHandler class has single method "hello" and it maps to the URL path "hello". This is general rule in WebPie - methods of handler classes map one to one to the elements of URI path. For example, we can add another method to our server called "time":

.. code-block:: python

    # hello_time.py
    
    from webpie import WPApp, WPHandler
    import time

    class MyHandler(WPHandler):                                             

            def hello(self, request, relpath):                              
                    return "Hello, World!\n"                                        

            def time(self, request, relpath):                             
                    return time.ctime()+"\n", "text/plain"          

    WPApp(MyHandler).run_server(8080)

Now our handler can handle 2 types of requests, it can say hello and it can tell local time:

.. code-block:: bash

	$ curl http://localhost:8080/hello
	Hello, World!
	$ curl http://localhost:8080/time
	Sun May  5 06:47:15 2019
	$ 
    
Nested Handlers
---------------
If needed, handlers can be nested. This will help structure your code better and will be reflected in
deeper structure of the URI.


.. code-block:: python

    # nested_handlers.py

    from webpie import WPApp, WPHandler
    import time

    class HelloHandler(WPHandler):                      #1 

        def hello(self, request, relpath):                              
            return "Hello, World!\n"                                        

    class ClockHandler(WPHandler):                      #2 

        def time(self, request, relpath):                       
            return time.ctime()+"\n", "text/plain"      #3

    class TopHandler(WPHandler):

        def __init__(self, *params):                    #4
            WPHandler.__init__(self, *params)
            self.greet = HelloHandler(*params)          
            self.clock = ClockHandler(*params)

        def version(self, request, relpath):            #5
            return "1.0.3"

    WPApp(TopHandler).run_server(8080)

#1: old "hello world" handler

#2: new time handler

#3: return time with Content-Type = "text/plain"

#4: top handler with 2 nested handlers

#5: top handler can have its own methods

The new app with the nested handler will respond to 2-level deep URIs. Top level of the URI path
will map to one of the two lower level handlers under the top handler. The second level path word
will be used as the method name under of the lower level handler.

Also notice that the top handler has its own method "version":

.. code-block:: bash

	$ curl http://localhost:8080/greet/hello
	Hello, World!
	$ curl http://localhost:8080/clock/time
	Sun May  5 06:49:14 2019
	$ curl http://localhost:8080/version
	1.0.2
	$ 
    
Callable Handler
----------------

If you make the Handler callable, the Handler itself will be called as if it was a web method
to process any request, which does not have a corresponding method defined:

.. code-block:: python

    # callable_handler.py

    from webpie import WPApp, WPHandler
    import json

        class MyApp(WPApp):

            def __init__(self, root_class):
                WPApp.__init__(self, root_class)
                self.Memory = {}

        class Handler(WPHandler):
    
            def keys(self, request, relpath):
                return (
                    json.dumps(list(self.App.Memory.keys()))+"\n", 
                    "text/json"
                )
    
            def __call__(self, request, relpath):   # 1
                var_name = relpath
                method = request.method             # 2
                if method.upper() == "GET":
                    value = self.App.Memory.get(var_name)
                else:
                    value = json.loads(request.body)
                    self.App.Memory[var_name] = value
                return json.dumps(value)+"\n", "text/json"
            
        MyApp(Handler).run_server(8080)

#1 this will be called if no method is defined for he URI

#2 request is a WebOb Request object


.. code-block:: bash

    $ curl http://localhost:8080/keys
    []
    $ curl http://localhost:8080/math
    null
    $ curl -X POST -d '{"e":2.71828, "pi":3.1415}' http://localhost:8080/math
    {"e": 2.71828, "pi": 3.1415}
    $ curl http://localhost:8080/keys
    ["math"]
    $ curl http://localhost:8080/math
    {"e": 2.71828, "pi": 3.1415}
    $ 

In simple cases, you can even use a Python function as a handler.

.. code-block:: python

    # function_app.py

    from webpie import WPApp

    def hello(request, relpath):
        who = relpath or "world"
        return "Hello, "+who, "text/plain"

    WPApp(reverse).run_server(8080)


The Shortest WebPie App
-----------------------

.. code-block:: python

    # lambda_app.py
    
    from webpie import WPApp
    
    WPApp(lambda request, relpath: 
            ("Hello, %s\n" % (relpath or "world",), "text/plain")
    ).run_server(8080)


Application and Handler Lifetime
--------------------------------

The WPApp object is created *once* when the web server instance starts and it persists until the server stops, whereas WPHandler object trees are created for each individual HTTP request from scratch. Handler object's App member always points to the Application object. This allows the Application object to keep some persistent information and let handler objects access it. For example, our clock application can also keep
track of the number of requests it has received:

.. code-block:: python

    # time_count.py
    from webpie import WPApp, WPHandler
    import time

    class Handler(WPHandler):                                               

        def time(self, request, relpath):               
            return "[%d]: %s\n" % (self.App.bump_counter(), time.ctime()), "text/plain"

    class App(WPApp):

        def __init__(self, handler_class):
            WPApp.__init__(self, handler_class)
            self.Counter = 0
        
        def bump_counter(self):
            self.Counter += 1
            return self.Counter

    App(Handler).run_server(8080)

.. code-block:: bash

    $ curl http://localhost:8080/time
    [1]: Sat May  2 07:01:55 2020
    $ curl http://localhost:8080/time
    [2]: Sat May  2 07:01:57 2020
    $ curl http://localhost:8080/time
    [3]: Sat May  2 07:01:58 2020
    
Thread Safety
-------------

The bump_counter method in the previous example is not thread-safe. Because the WebPie's HTTP server
runs multiple threads, a thread per request, there is a possibility that the bump_counter method
will be called by two threads at (almost) the same time and the responses to both
requests will contain the same counter value.

To help make the code thread safe, WebPie offers "atomic" decorator. It can be used to make any method of
a Handler or the App class atomic and thread safe. Here is how the previous example can be fixed:

.. code-block:: python

    # time_count_thread_safe.py
    from webpie import WPApp, WPHandler, atomic
    import time

    class Handler(WPHandler):                                               

        def time(self, request, relpath):               
            return "[%d]: %s\n" % (self.App.bump_counter(), time.ctime()), "text/plain"

    class App(WPApp):

        def __init__(self, handler_class):
            WPApp.__init__(self, handler_class)
            self.Counter = 0
    
        @atomic
        def bump_counter(self):
            self.Counter += 1
            return self.Counter

    App(Handler).run_server(8080)

App Object as a Context Manager
-------------------------------
Another way to implement a critical section is to use the WPApp object as the context manager:


.. code-block:: python

    # getset.py

    from webpie import WPApp, WPHandler

    class MyApp(WPApp):

        def __init__(self, root_class):
            WPApp.__init__(self, root_class)
            self.Memory = {}

    class Handler(WPHandler):

        def set(self, req, relpath, name=None, value=None, **args):
            with self.App:
                self.App.Memory[name]=value
            return "OK\n"
    
        def get(self, req, relpath, name=None, **args):
            with self.App:
                return self.App.Memory.get(name, "(undefined)") + "\n"
    
    MyApp(Handler).run_server(8080)



Static Content
--------------

Sometimes the application needs to be able to deliver static content like HTML documents, 
CSS stylesheets, JavaScript code.
WebPie App can be configured to serve static file from certain directory in the file system.
By default, for security reasons, this feature is disabled. To enable it, call the WPApp constructor
with "static_location" argument pointing to the directory where your static content is. "static_path"
defines the top of the URI path to be mapped to that directory.

.. code-block:: python

    # static_server.py

    from webpie import WPApp, WPHandler
    import time

    class TimeHandler(WPHandler):
    
        def time(self, request, relpath, **args):
            return """
                <html>
                <head>
                    <link rel="stylesheet" href="/static/style.css" type="text/css"/>
                </head>
                <body>
                    <p class="time">%s</p>
                </body>
                </html>
            """ % (time.ctime(time.time()),)

    WPApp(TimeHandler, 
        static_location="./static_content", 
        static_path="/static"
        ).run_server(8080)
    

Session Management
------------------


Jinja2 Environment
------------------

WebPie is aware of Jinja2 template library and provides some shortcuts in using it.

To make your application work with Jinja2, you need to initialize Jinja2 environment first:

.. code-block:: python

    from webpie import WPApp, WPHandler		
    
    class MyHandler(WPHandler):    
        # ...


    class MyApp(WPApp):
        # ...

    application = MyApp(MyHandler)
    application.initJinjaEnvironment(
        tempdirs = [...],
        filters = {...},
        globals = {...}
    )

The initJinjaEnvironment method accepts 3 arguments:

tempdirs - list of directories where to look for Jinja2 templates,
  
filters - dictionary with filter names and filter functions to add to the environment,
  
globals - dictionary with "global" variables, which will be added to the list of variables when a template is rendered
  
  
Here is an example of such an application and corresponding template:


.. code-block:: python

    # templates.py
    from webpie import WPApp, WPHandler
    import time

    Version = "1.3"

    def format_time(t):
        return time.ctime(t)

    class MyHandler(WPHandler):						

        def time(self, request, relpath):
            return self.render_to_response("time.html", t=time.time())
        
    application = WPApp(MyHandler)
    application.initJinjaEnvironment(
        ["samples"], 
        filters={ "format": format_time },
        globals={ "version": Version }
        )
    application.run_server(8080)

and the template samples/time.html is:

.. code-block:: html

    <html>
    <body>
    <p>Current time is {{t|format}}</p>
    <p style="float:right"><i>Version: {{version}}</i></p>
    </body>
    </html>

In this example, the application initializes the Jinja2 environment with "samples" as the templates location,
function "format_time" becomes the filter used to display numeric time as date/time string and "global"
variable "version" is set to the version of the code.

Then the handler calls the "render_to_response" method, inherited from WPHandler, to render the template "time.html"
with current time passed as the "t" argument, and implicitly "version" passed to the rendering as a global
variable. The "render_to_response" method renders the template and returns properly constructed Response
object with content type set to "text/html".

Strict Applications
-------------------

As long as a method of the Handler class has suitable arguments, it can be called by including its name in the URI.
This can be dangerous because a malicious user, who has access to the source code of your application, can
invoke a code, which was not meant to be available from the outside. To protect a Handler from this,
add a list of allowed web method names as a _Methods class member to your Handler definition:


.. code-block:: python

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
                return 401

    WPApp(StrictHandler).run_server(8080)                   

#1 Only methods with names listed are allowed as web methods

#2 We do not want this function to be exposed as a web method

#3 Another shortcut - return standard HTTP response for given status code 