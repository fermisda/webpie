WebPie URI-to-web method mapping, detailed
==========================================

Here is what actually happens when a WebPie application receives a request for a URI like this: /a/b/c/.../d?x=y&z=q:

0. Create a WebOb Request object and let it parse the WSGI environment.
#. Extract the URI path (/a/b/c/.../d) and the query arguments (x=y&z=q) from the WebOb object.
#. Creates arguments dictionary ``{"x":"y", "z":"q"}``.
#. Break the URI path into pieces ``["a","b","c",..."d"]``.
#. Set ``unseen_path`` to ``["a","b","c",..."d"]``.
#. Create the top Handler object and make the top Handler ``current handler``.
#. Loop:

        a. If the ``current handler`` is callable, set ``callable`` to the ``current handler`` break out of the loop.
        b. If the ``unseen path`` is empty, exit with error -- invalid path
        c. Remove first element from the ``unseen_path`` and remember it as ``method``
        d. If the ``current handler`` is a WPHandler object and it has an attribute named as ``method``:
            
            * Set ``current handler`` to the method of the ``current handler``
            * continue the Loop
        
        e. Otherwise, exit with error

#. join ``unused path`` into relpath and call the ``callable``:

    .. code-block:: python

        response = callable(request,    # original WebOb Request object
            "/".join(unused_path),      # joined unused path
            **arguments                 # query arguments
        )

In plain English: URI is mapped to actual web method by going down the tree of WPHandler obcjets starting from the top Handler, 
looking for first callable and calling it as a web method,
passing it the WebOb Request, unused portion of the path and query arguments.

Examples
--------

.. code-block:: python

    class H1(WPHandler):
    
        def say(self, request, relpath, what="hello", **therest):
            # only "what" query argument will be used. 
            # The rest will be accepted, but ignored
            return relpath or what

    class Hander(WPHandler):
    
        def __init__(self, *params):
            WPHandler.__init__(self, *params)
            self.down = H1(*params)
    
        def hello(self, request, relpath, **args):
            return relpath
            
        def no_args(self, request, relapth):
            return "OK"
            
        def few_args(self, request, relapth, x=None, b="yes"):
            return "OK"
            
    app = WPApp(Hander)
            
This handler will respond to URIs:

.. code-block:: shell

    /hello                  # relpath="",       args={}
    /hello/there            # relpath="there",  args={}
    /hello?a=b              # relpath="",       args={"a":"b"}
    /hi                     # error - web method not found
    /no_args                # relpath=""
    /no_aggs?x=y            # error - the web method does not expect 
                            #         any query arguments
    /few_aggs/abc?x=y       # relpath = "abc",  x="y", b="yes"
    /few_aggs?b=no          # relpath = "",     x=None, b="no"
    /down/say?what=hi       # relpath = "",     what="hi",      reply: "hi"
    /down/say?x=unused      # relpath = "",     what="hi",      reply: "hi"
    /down/say/hi            # relpath = "hi",   what="hello",   reply: "hi"
    /down/say               # relpath = "",     what="hello",   reply: "hello"
    
A Handler, which will accept any URI:
 
.. code-block:: python

    class AcceptAll(WPHandler):
    
        def __call__(self, request, relpath, **args):
            return f"""
                relpath:    {relpath}\n
                query args: {args}\n
            """
            
    app = WPApp(AcceptAll)

In simple cases, there is no need to create WPHandler explicitly:
    
.. code-block:: python

    def hello_world(request, relpath, **args):
        from = f" from {relpath}" if relpath else ""
        return f"Hello World!{form}"
    
    WPApp(hello_world).run_server(8080)

Or even shorter, but less readable, unless you are into functional programming:

.. code-block:: python

    from webpie import WPApp

    WPApp(lambda q,p,x: f"{(((int(x)+19)**3)%101)}").run_server(8888)

    


