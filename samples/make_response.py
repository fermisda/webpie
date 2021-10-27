from webpie import WPApp

def build_response(request, relpath, **args):
    
    out_list = []
    
    items = {
        'i':    200,
        'd':    args,
        's':    "string",
        'b':    b"bytes",
        'l':    ["a\n", "b\n", "c\n"],
        'g':    (x for x in ["aa\n", "bb\n", "cc\n"]),
        't':    "text/plain"
    }
    
    
    for c in (relpath or ""):
        out_list.append(items[c])
        
    if len(out_list) == 1:  out = out_list[0]
    else:   out = tuple(out_list)
    print("returning:", out)
    return out
    
WPApp(build_response).run_server(8888)
