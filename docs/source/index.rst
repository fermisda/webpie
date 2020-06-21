.. WebPie documentation master file, created by
   sphinx-quickstart on Wed May  6 12:08:01 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

WebPie Documentation
====================

.. image:: https://img.shields.io/pypi/l/webpie.svg
    :target: https://pypi.org/project/webpie/

.. image:: https://img.shields.io/pypi/wheel/webpie.svg
    :target: https://pypi.org/project/webpie/

.. image:: https://img.shields.io/pypi/pyversions/webpie.svg
    :target: https://pypi.org/project/webpie/

WebPie (pronounced: web-py) is a intuitive, simple yet powerful object-oriented web applications development framework for Python.

Installation
------------

You can install WebPie from PyPi:

.. code-block:: bash

	pip install webpie
	
Quick Start
-----------

WebPie says Hello, World !
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is the WebPie "Hello, World!" application:

.. code-block:: python

    # hello_world.py

    from webpie import WPApp, WPHandler

    class HelloHandler(WPHandler):                      

        def hello(self, request, relpath):           
            return "Hello, World!"                 

    application = WPApp(HelloHandler)
    application.run_server(8080)        

Now you can run this script as a stand-alone web server:

.. code-block:: shell

    $ python hello_world.py &
    [1] 34509
    
    $ curl http://localhost:8080/hello
    Hello, World!

WebPie Anatomy
~~~~~~~~~~~~~~

The "Hello, World!" sample illustrates the basic structure of a WebPie application. It consists of a Request Handler class and an Application object.
The Request Handler (or Handler) class has to be a subclass of ``WPHandler`` and the application object is an object of WPApp class or its customized sublass.

When the WepPie web server starts, it creates the WPApp object, which exists as long as the web server runs. 
Then the App object creates new new Handler object for every request the server receives to process it. That is why the App object
is constucted with the Handler class as its argument instead of an object of the Handler class.
The Handler object is transient and short-lived - it is destroyed after processing the request. 
Handler objects have reference to the persistent WPApp object and can use the latter to store some persistent context information.

To be able to process requests, the Handler has to define one or more *web methods*. Most generally, a web method must look like this:

.. code-block:: python

    class MyHandler(WPHandler):
    
        def web_method(self, request, relpth, **args):
            # ...
            return Response(...)

Without getting into too much details at this point,
a web method receives the HTTP request parsed into WebOb Request object as its ``request`` argument and is suposed to return a WebOb Response
object. There are some handy shortcuts, however. The web method does not always have to return the Response object. Instead, it can
return many different things. As you saw in the samples above, it can also return just a string.
There is some function inside WebPie which intelligently converts web method's return into a Response
object.

URL Mapping
~~~~~~~~~~~

Notice that the Hello World server responded to URI path ending with ``hello``, which happens to be the name of the method of the ``HelloHandler`` class. 
This is how WebPie works - basically, it maps URI path to a web method of a Handler. Here is a Handler with two web methods:

.. code-block:: python

    # clock.py

    from webpie import WPApp, WPHandler                       
    import time

    class Clock(WPHandler):                                

        def ctime(self, request, relpath):          
            return "%s\n" % time.ctime()

        def clock(self, request, relpath):          
            return "%f\n" % time.time()

    WPApp(Clock).run_server(8080)

This web application will respond to 2 URIs:

.. code-block:: shell

    $ python clock.py &
    [2] 35059

    $ curl http://localhost:8081/clock
    1592657444.597579

    $ curl http://localhost:8081/ctime
    Sat Jun 20 07:50:48 2020

Handlers can be nested to be able to work with longer URI paths:

.. code-block:: python

    from webpie import WPApp, WPHandler                       
    import time

    class Clock(WPHandler):                                

        def ctime(self, request, relpath):          
            return "%s\n" % time.ctime()

        def clock(self, request, relpath):          
            return "%f\n" % time.time()

    class Greeter(WPHandler):                                
    
        def hello(self, request, relpath, **args):           
            return "Hello, World!\n"           
            
    class Top(WPHandler):
    
        def __init__(self, app):
            WPHandler.__init__(self, request, app)
            self.clock = Clock(request, app)
            self.greet = Greeter(request, app)

    WPApp(Top).run_server(8080)                         

Notice that the ``Top`` Handler now has 2 sub-handlers members - ``clock`` and ``greeter``. These member names will map onto the request URI
parts:

.. code-block:: shell

    $ curl http://localhost:8080/clock/ctime
    Fri Jun 19 11:26:53 2020
    
    $ curl http://localhost:8080/greet/hello
    Hello, World!
    $

As mentioned above, ``WPApp`` class implements standard WSGI interface, so any object of a ``WPApp`` subclass can be used anywhere a WSGI application
can be used. Instead of running our app on its own, it can be plugged into a WSGI-compatibe HTTP server, such as uWSGI:

.. code-block:: python

    # clock.py

    from webpie import WPApp, WPHandler

    class Clock(WPHandler):                                

        def ctime(self, request, relpath):          
            return "%s\n" % time.ctime()

        def clock(self, request, relpath):          
            return "%f\n" % time.time()

    application = WPApp(Clock)

.. code-block:: bash

	$ uwsgi --http :8080 --wsgi-file hello_world_wsgi.py

And you can run the same code in both ways:

.. code-block:: python

    from webpie import WPApp, WPHandler

    class Clock(WPHandler):                                

        def ctime(self, request, relpath):          
            return "%s\n" % time.ctime()

        def clock(self, request, relpath):          
            return "%f\n" % time.time()

    application = WPApp(Clock)
    
    if __name__ == "__main__":
        # running stand-alone
        application.run_server(8080)
    else:
        # imported module
        pass



More Details
------------

.. toctree::
   :maxdepth: 2

   by_sample
   uri_mapping

