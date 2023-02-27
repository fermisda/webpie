from webpie import WPApp, WPHandler, sanitize

class H(WPHandler):
   
    @sanitize(only="a", unsafe_re="ab?cc")
    def env(self, req, relpath, **args):
        lines = (
            ["request.environ:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in sorted(req.environ.items())]
            + ["\nrelpath: %s" % (relpath or "")]
            + ["\nargs:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in args.items()]
            + ["\nrequest.GET:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in req.GET.items()]
            + ["\nrequest.POST:"]
            + ["  %s = %s" % (k, repr(v)) for k, v in req.POST.items()]
        )
        return "\n".join(lines) + "\n", "text/plain"

class App(WPApp):

    def __init__(self, handler):
        WPApp.__init__(self, handler)

application = App(H)

if __name__ == "__main__":
    application.run_server(8080)
    
