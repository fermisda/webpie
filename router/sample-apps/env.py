from webpie import WPApp

def env(request, relpath):
    out = [
        f"{k}: {v}\n" for k, v in request.environ.items()
    ]
    return out, "text/plain"

application = WPApp(env)