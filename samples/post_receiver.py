from webpie import WPApp, WPHandler

class Handler(WPHandler):

        def post(self, request, relpath, **args):
                print("Request method:", request.method)
                print("Request headers:")
                for h, v in request.headers.items():
                        print("%s: %s" % (h,v))
                print("Body length:", len(request.body_file.read()))
                return "OK\n"

WPApp(Handler).run_server(8080)
