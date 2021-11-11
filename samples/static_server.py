# static_server.py

from webpie import WPApp, WPStaticHandler

WPApp(WPStaticHandler).handler_options("./static", cache_ttl=300).run_server(8080)
