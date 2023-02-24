import re
from .webob.exc import HTTPBadRequest
from urllib.parse import quote

def sanitize(exclude=[], only=None, unsafe=r"<'>\|;", safe_re=None, unsafe_re=None, sanitizer=None):
    uns = unsafe
    safe_re = None if safe_re is None else re.compile(safe_re)
    unsafe_re = None if unsafe_re is None else re.compile(unsafe_re)

    def sanitize_value(name, value):
        #print("_check_unsafe_sanitizer: name=", name, "   value:", value)
        if isinstance(value, str):
            if uns is not None and any(c in value for c in uns) \
                        or unsafe_re is not None and unsafe_re.fullmatch(value) \
                        or safe_re is not None and not safe_re.fullmatch(value):
                raise HTTPBadRequest("Invalid value for " + quote(name))

    sanitizer = sanitizer or sanitize_value

    def decorator(method):
        #onl = only
        #excl = exclude
        def decorated(handler, request, relpath, *params, **args):
            if "(relpath)" not in exclude:  
                sanitizer('(relpath)', relpath)

            for name, value in args.items():
                if value is not None and name not in exclude and (only is None or name in only):
                    if not isinstance(value, list):
                        value = [value]
                    [sanitizer(name, v) for v in value]
        
            for name, value in request.params.items():
                if value is not None and name not in exclude and (only is None or name in only):
                    sanitizer(name, value)
            
            return method(handler, request, relpath, *params, **args)
        return decorated
    return decorator

