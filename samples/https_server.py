from webpie import HTTPSServer
import sys

def app(env, start_response):
    start_response("200 OK", [("Content-type","text/plain")])
    return ["Hello world\n"]

port, cert, key = sys.argv[1:]
port = int(port)

srv = HTTPSServer(port, app, cert, key)
srv.start()
srv.join()
