Details
=======

Web Methods in Details
----------------------

The WebPie server handler method has 2 fixed arguments and optional keyword arguments.

First argiment is the request object, which encapsulates all the information about the incoming HTTP request. Currently WebPie uses WebOb library Request and Response classes to handle HTTP requests and responses.

Arguments
~~~~~~~~~

Most generally, web method looks like this:

.. code-block:: python

    def method(self, request, relpath, **url_args):
        # ...
        return response


Web method arguments are:

request
.......

request is WebOb request object built from the WSGI environment. For convenience, it is also available as the handler's
Request member.

relpath
.......

Sometimes, while walking down the tree of handlers to find the method to handle the request, there will be some
unused portion of URI after the name of the target handler method. For example, in our clock example, we may want to
structure our URL to specify the field of the current time we want to see in the following way:

.. code-block::

	http://localhost:8080/time/month    # month only
	http://localhost:8080/time/minute   # minute only
	http://localhost:8080/time          # whole day/time

In this case, we want the "time" method to hadle all types of requests and know which portion of date/time to
return. Here is the code which does this:

.. code-block:: python

	from webpie import WPApp, WPHandler
	from datetime import datetime

	class MyHandler(WPHandler):						

		def time(self, request, relpath):			
			t = datetime.now()
			if not relpath:
				return str(t)+"\n"
			elif relpath == "year":
				return str(t.year)+"\n"
			elif relpath == "month":
				return str(t.month)+"\n"
			elif relpath == "day":
				return str(t.day)+"\n"
			elif relpath == "hour":
				return str(t.hour)+"\n"
			elif relpath == "minute":
				return str(t.minute)+"\n"
			elif relpath == "second":
				return str(t.second)+"\n"

	application = WPApp(MyHandler)
	application.run_server(8080)

url_args
........

Anoter, perhaps more conventional way of doing this is to use so called query parameters to specify the
format of the date/time representation, e.g.:

.. code-block::

	http://localhost:8080/time?field=minute

WebPie always parses query parameters and passes them to the handler method as if they were keyword arguments. 
For example, we can write the method which extracts fields from current time like this:

.. code-block:: python

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


and then call it like this:

.. code-block:: bash

	$ curl  http://localhost:8080/time
	2019-05-05 08:39:49.593855
	$ curl  "http://localhost:8080/time?field=month"
	5
	$ curl  "http://localhost:8080/time?field=year"
	2019

Return Value
~~~~~~~~~~~~
The output of a web method is a Response object. Conveniently, there is a number of ways to return something from the web method. Ultimately, all of them are used to produce and return the Response object. Here is a list of possibile returns from the web oject and how the framework
converts the output to the Response object:

======================================  =================================== ==================================================================
return                                  example                             equivalent Response object
======================================  =================================== ==================================================================
Response object                         Response("OK")                      same - Response("OK")
text                                    "hello world"                       Response("hello world")
text, content type                      "OK", "text/plain"                  Response("OK", content_type="text/plain")
text, status                            "Error", 500                        Response("Error", status_code=500)
text, status, content type              "Error", 500, "text/plain"          Response("Error", status_code=500, content_type="text/plain")
text, headers                           "OK", {"Content-Type":"text/plain"} Response("OK", headers={"Content-Type":"text/plain"})
list                                    ["Hello","world"]                   Response(app_iter=["Hello","world"])
iterable                                (x for x in ["hi","there"])         Response(app_iter=(x for x in ["hi","there"]))
iterable, content_type
iterable, status, content_type
iterable, status, headers
======================================  =================================== ==================================================================

The response body can be returned either as a single string or bytes object, or as a list of strings or
bytes objects or as an iterable (generator or iterator), producing a sequence of strings or bytes objects.
If the handler method returns strings, under Python3, they will be converted to bytes using UTF-8 conversion.
If you want to use some other encoding, then you must convert your strings to bytes before returning
from the handler method.


Static Content
--------------

Sometimes the application needs to serve static content like HTML documents, CSS stylesheets, JavaScript code.
WebPie App can be configured to serve static file from certain directory in the file system.


.. code-block:: python

    class MyHandler(WPHandler):
        #...

    class MyApp(WPApp):
        #...
        
    application = MyApp(MyHandler, 
            static_enabled = True,
            static_path = "/static", 
            static_location = "./scripts")
            
    application.run_server(8002)
    
    
If you run such an application, a request for URL like "http://..../static/code.js" will result in
delivery of file local file ./scripts/code.js. static_location can be either relative to the working
directory where the application runs or an absolute path.

Because serving files from local file system is a potential security vulnerability, this
functionality must be explicitly enabled with static_enabled=True. static_path and static_locations
have defaults:

.. code-block:: python

    static_path = "/static"
    static_location = "./static"

Threaded Applications
---------------------
WebPie provides several mechanisms to build thread safe applications. When working in multithreaded environment, WebPie Handler
objects are concurrently created in their own threads, one for each request, whereas WebApp object is created only once and it
is shared by all the threads handling the requests. This feature makes it possible to use the App object for inter-handler
synchronization. The App object has its own lock object and threads can use it in 2 different ways:

atomic decorator
~~~~~~~~~~~~~~~~
Decorating a web method with "atomic" decorator makes the web method atomic in the sense that if a handler thread enters such
a method, any other handler thread of the same application will block before entering any atomic method until the first thread returns from the method.

For example:

.. code-block:: python

    from webpie import WPApp, WPHandler, atomic

    class MyApp(WPApp):
    
        def __init__(self, root_class):
            WPApp.__init__(self, root_class)
            self.Memory = {}
    
    class Handler(WPHandler):
    
        @atomic
        def set(self, req, relpath, name=None, value=None, **args):
            self.App.Memory[name]=value
            return "OK\n"
        
        @atomic
        def get(self, req, relpath, name=None, **args):
            return self.App.Memory.get(name, "(undefined)")+"\n"
        
    application = MyApp(Handler)
    application.run_server(8002)

You can also decorate methods of the App. For example:

.. code-block:: python

	from webpie import WPApp, WPHandler, atomic

	class MyApp(WPApp):
    
	    RecordSize = 10
    
	    def __init__(self, root_class):
	        WPApp.__init__(self, root_class)
	        self.Record = []
        
	    @atomic
	    def add(self, value):
	        if value in self.Record:
	            self.Record.remove(value)
	        self.Record.insert(0, value)
	        if len(self.Record) > self.RecordSize:
	            self.Record = self.Record[:self.RecordSize]
        
	    @atomic
	    def find(self, value):
	        try:    i = self.Record.index(value)
	        except ValueError:
	            return "not found"
	        self.Record.pop(i)
	        self.Record.insert(0, value)
	        return str(i)
        
	class Handler(WPHandler):
    
	    def add(self, req, relpath, **args):
	        return self.App.add(relpath)
        
	    def find(self, req, relpath, **args):
	        return self.App.find(relpath)
        
	application = MyApp(Handler)
	application.run_server(8002)


App object as a context manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Another to implement a critical section is to use the App object as the context manager:


.. code-block:: python

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
        
    application = MyApp(Handler)
    application.run_server(8002)


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

Advanced Topics
---------------

Permissions
~~~~~~~~~~~

Strict Applications
~~~~~~~~~~~~~~~~~~~

Built-in HTTP/HTTPS Server
~~~~~~~~~~~~~~~~~~~~~~~~~~
