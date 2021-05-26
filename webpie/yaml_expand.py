import re

subst = re.compile("(%\((\w+)\))")

def expand_str(text, vars):
    out = []
    i0 = 0
    for m in subst.finditer(text):
        name = m.group(2)
        i1 = m.end(1)
        if name in vars:
            out.append(text[i0:m.start(1)])
            out.append(str(vars[name]))
        else:
            out.append(text[i0:i1])
        i0 = i1
    out.append(text[i0:])
    return "".join(out)


def yaml_expand(item, vars={}):
    #print("yaml_expand: input:", item, "    vars:", vars)
    if isinstance(item, str):
        item = expand_str(item, vars)
    elif isinstance(item, dict):
        new_vars = {}
        new_vars.update(vars)

        # substitute top level strings only
        out = {k:expand_str(v, vars) for k, v in item.items() if isinstance(v, str)}

        # use this as the substitution dictionary
        new_vars.update(out)    
        out.update({k:yaml_expand(v, new_vars) for k, v in item.items()})
        item = out
    elif isinstance(item, list):
        item = [yaml_expand(x, vars) for x in item]
    #print("yaml_expand: output:", item)
    return item
            
