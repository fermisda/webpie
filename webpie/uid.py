from pythreader import Primitive, synchronized
import string, random


class _UIDGen(Primitive):
    
    def __init__(self, tag="", range=1000000):
        Primitive.__init__(self)
        self.Next = 0
        self.Tag = tag
        self.Range = range

    _alphabet=string.ascii_lowercase + string.ascii_uppercase

    @synchronized
    def get(self, as_int=False):
        self.Next = (self.Next + 1) % self.Range
        u = self.Next
        if not as_int:
            a1 = random.choice(self._alphabet)
            a2 = random.choice(self._alphabet)
            a3 = random.choice(self._alphabet)
            u = "%s%s%s.%03d" % (a1, a2, a3, u%1000)
            if self.Tag:
                u = self.Tag + "." + u
        return u
            
        

_uid = _UIDGen()

def uid(u=None, as_int=False, tag=""):
    global _uid
    if u is not None:   return u
    u = _uid.get(as_int)
    return u
    
def init(tag=""):
    global _uid
    _uid = _UIDGen(tag)
    
    
