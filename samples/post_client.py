from urllib.request import urlopen, Request

import sys

data = sys.stdin.read().encode("utf-8")
request = Request("http://localhost:8080/echo", data=data)
response = urlopen(request)
print(response)
print(response.read().decode())