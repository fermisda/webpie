.. WebPie documentation master file, created by
   sphinx-quickstart on Wed May  6 12:08:01 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

WebPie - web applications framework for Python
==============================================

.. image:: https://img.shields.io/pypi/l/webpie.svg
    :target: https://pypi.org/project/webpie/

.. image:: https://img.shields.io/pypi/wheel/webpie.svg
    :target: https://pypi.org/project/webpie/

.. image:: https://img.shields.io/pypi/pyversions/webpie.svg
    :target: https://pypi.org/project/webpie/





**WebPie** (pronounced: web-py) is a simple, elegant, object-oriented web applications development framework for Python.

Here is how **WebPie** says "Hello, World!"::

	from webpie import WPApp, WPHandler

	class MyHandler(WPHandler):                      

	    def hello(self, request, relpath):           
	        return "Hello, World!"                 

	app = WPApp(MyHandler)             


And here is a bit less human-readable way of doing the same::

	from flask import Flask
	app = Flask(__name__)

	@app.route('/')
	def hello_world():
	    return 'Hello, World!'

In fact, with WebPie it can be even shorter, but still readable, although not really object - oriented any more::

    from webpie import WPApp
    def hello(request, relpath):    return "Hello, World!"
    app = WPApp(hello)

WebPie main features
--------------------
- Write your code in an intuitive way, as a set of classes, not a module with bunch of unrelated functions
- URL structure maps one-to-one to the server code structure
- Receive and process URI query arguments as method named arguments
- Support for static contents
- WebPie App is a standard WSGI application, so it can be plugged into any popular HTTP srever with WSGI support
- WebPie comes with its own HTTP/HTTPS server class, which can be used for light weight applications
- Support for sessions
- WebPie App object persists between requests, so it can be used to keep long-term context, database connections, etc.
- WebPie helps you build multi-threaded web servrices easily
- WebPie is Jinja2-friendly
- WebPie comes with its own WebSockets server implementation module
- Python 2.7 and 3.7-3.8 supported
- WebPie uses WebOb to parse and represent the HTTP request


More Details
------------

.. toctree::
   :maxdepth: 2

   by_sample

