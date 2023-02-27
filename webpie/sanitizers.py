import re
from .webob.exc import HTTPBadRequest
from urllib.parse import quote

def sanitize(exclude=[], only=None, unsafe=r"<'>\|", safe_re=None, unsafe_re=None, ignore_payload=True, sanitizer=None):
    safe_re = None if safe_re is None else re.compile(safe_re)
    unsafe_re = None if unsafe_re is None else re.compile(unsafe_re)
    if isinstance(exclude, str):
        exclude = [exclude]
    if isinstance(only, str):
        only = [only]

    def sanitize_generic(name, value):
        #print("_check_unsafe_sanitizer: name=", name, "   value:", value)
        if isinstance(value, str):
            invalid = unsafe_re is not None and unsafe_re.search(value) \
                        or unsafe is not None and any(c in value for c in unsafe)
            invalid = invalid and not (safe_re is not None and safe_re.fullmatch(value))
            if invalid:
                raise HTTPBadRequest("Invalid value for " + quote(name))

    sanitizer = sanitizer or sanitize_generic

    def decorator(method):
        onl = only
        excl = exclude
        def decorated(handler, request, relpath, *params, **args):
            if "(relpath)" not in excl:  
                sanitizer('(relpath)', relpath)

            for name, value in args.items():
                if value is not None and name not in exclude and (onl is None or name in only):
                    if not isinstance(value, list):
                        value = [value]
                    [sanitizer(name, v) for v in value]

            params = request.GET.items() if ignore_payload else request.params.items()
            for name, value in params:
                if value is not None and name not in exclude and (onl is None or name in onl):
                    sanitizer(name, value)
            
            return method(handler, request, relpath, *params, **args)
        return decorated
    return decorator

