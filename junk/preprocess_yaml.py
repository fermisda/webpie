import re

subst = re.compile("(%\((\w+)\))")

def substitute_str(text, vars):
    out = []
    i0 = 0
    for m in subst.finditer(text):
        name = m.group(2)
        if name in vars:
            out.append(text[i0:m.start(1)])
            out.append(str(vars[name]))
            i0 = m.end(1)
    out.append(text[i0:])
    return "".join(out)
        
def substitute_list(lst, vars):
    return [substitute_in(item, vars) for item in lst]
    
def substitute_dict(d, outer):
    
    vars = {}
    vars.update(outer)

    # substitute top level strings only
    out = {k:substitute_str(v, outer) for k, v in d.items() if isinstance(v, (str, int))}

    # use this as the substitution dictionary
    vars.update(out)    
    out.update({k:substitute_in(v, vars) for k, v in d.items()}

    return out
    
def substitute_in(item, vars)
    if isinstance(item, str):
        item = substitute_str(item, vars)
    elif isinstance(item, dict):
        item = substitute_dict(item, vars)
    elif isinstance(item, list):
        item = substitute_list(item, vars)
    return item
        
    

def preprocess(s, vars={}):
    return substitute_in(s, vars)
            
        
    
            