Web Method in Details
=====================

Any function or a class method which looks like this can be a web method:

.. code-block:: python

    from webpie import Response

    class Handler(WPHandler):
    
        def method(self, request, relpth, **args):
            # ...
            return Response(...)

    def method(request, relpth, **args):
        # ...
        return Response(...)

A web method accepts 2 positional arguments:

    **request** - `WebOb <https://webob.org/>`_  `Request <https://docs.pylonsproject.org/projects/webob/en/stable/reference.html#request>`_ object
    
    **relpath** - Portion of the request URI left unused after the web method was found (see `URI Mapping <uri_mapping.html>`_)
    
URI query arguments are parsed into the ``**args`` key/value portion of the method arguments.

A web method is supposed to return a `WebOb <https://webob.org/>`_  `Response <https://docs.pylonsproject.org/projects/webob/en/stable/reference.html#response>`_ object.
WebPie re-exports WebOb's ``Response`` class, so you can import it from webpie module.
Strictly for convenience, a web method can also return its output not only as a ``Response`` object, but also in many different ways, 
and the WebPie will convert the output into the Response object.
Here are some possibilities and how they are interpreted:


====================================== =========================== ==================================== ==================================================================
return types                           interpretation              example                              equivalent Response object
====================================== =========================== ==================================== ==================================================================
Response object                                                    Response("OK")                       same - Response("OK")
str/bytes                              response body               "hello world"                        Response("hello world")
str/bytes, str                         body, content type          "OK", "text/plain"                   Response("OK", content_type="text/plain")
str/bytes, int                         body, status.               "Error", 500                         Response("Error", status_code=500)
str/bytes, int, str                    body, status, content type  "Error", 500, "text/plain"           Response("Error", status_code=500, content_type="text/plain")
str/bytes, dict                        body, headers               "OK", {"Content-Type":"text/plain"}  Response("OK", headers={"Content-Type":"text/plain"})
list                                   body iterator               ["Hello","world"]                    Response(app_iter=["Hello","world"])
iterable                               body iterator               (x for x in ["hi","there"])          Response(app_iter=(x for x in ["hi","there"]))
iterable, str                          body iterator, content type (x for x in "hello"), "text/plain"   Response(app_iter=(x for x in "hello"), content_type="text/plain")
iterable, int, str                     body iterator, status,      lines(), 200, "text/csv"
                                       content type
iterable, int, dict                    body iterator, status,      lines(), 200, 
                                       headers                     {"Content-Type":"text/csv",
                                                                   "Cache-Control":"max-age: 3600"}
====================================== =========================== ==================================== ==================================================================

Redirection
-----------
A web method can call WPHandler's ``redirect`` method. This method generates a special exception, which is interpreted by WebPie, so you do
not have to worry about explicitly ending the web method execution after calling the ``redirect``. For example:

.. code-block:: python

    class Handler(WPHandler):
    
        def main(self, request, relpath):
            if not self.App.user_authenticated(request):
                self.redirect("/login_form")
            # ...
            
        def login_form(self, request, relpath):
            self.render_to_response("login.html")   # form with action="./authenticate"
            
        def authenticate(self, request, relpath):
            if self.App.authenticate_user(request):
                self.redirect("./main")
            else:
                self.redirect()