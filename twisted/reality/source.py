import types
import string

import cStringIO
StringIO = cStringIO
del cStringIO

# Twisted Imports
from twisted.python import observable, reflect

# Sibling Imports
import thing

# blek; source sanitization routines
def sanitizeTuple(o):
    """Tuple version of sanitizeList.
    """
    return tuple(sanitizeList(o))

def sanitizeInstance(o):
    """If possible, sanitize the given instance so it is source-persistent.
    """
    if reflect.isinst(o,thing.Thing):
        return SourceThing(o)
    if reflect.isinst(o,observable.Hash):
        return SourceHash(o)
    else: return o # flag a warning here; you're screwed

def sanitizeMethod(o):
    """If this is a method of a Thing, sanitize it.
    Otherwise, write out the method.
    """
    if reflect.isinst(o.im_self,thing.Thing):
        return SourceMethod(o)
    else:
        return o # screwed here too...

def sanitizeList(o):
    """Return a sanitized version of the list for source persistence.
    """
    return map(sanitize,o)

def sanitizeDict(o):
    """Return a SourceDict for source persistence.
    """
    n={}
    for k,v in o.items():
        n[k]=sanitize(v)
    return SourceDict(n)

def sanitizeClass(o):
    """Return a classname for source persistence.
    """
    return SourceRaw(o.__module__ + "." + o.__name__)

def sanitize(o):
    """'Clean' a particular string for source persistence.
    """
    try:
        action={types.InstanceType: sanitizeInstance,
                types.ListType:     sanitizeList,
                types.DictType:     sanitizeDict,
                types.TupleType:    sanitizeTuple,
                types.MethodType:   sanitizeMethod,
                types.ClassType:    sanitizeClass}[type(o)]
    except KeyError:
        return o # you *may* also be screwed here; but this also
                 # works for stuff like strings
    else:
        return action(o)

class SourceRaw:
    """raw string for source persistence.
    """
    def __init__(self, s):
        """Initialize.
        """
        self.s = s
    def __repr__(self):
        """Represent.
        """
        return self.s

class SourceMethod:
    """pretty-printed method for source persistence.
    """
    def __init__(self,m):
        """Initialize.
        """
        self.method=m
    def __repr__(self):
        """Represent.
        """
        return "m(%s,%s)"%(repr(self.method.im_self.name),
                           repr(self.method.__name__))

class SourceDict:
    """pretty-printed dict for source persistence.
    """
    def __init__(self,d):
        """Initialize.
        """
        self.dict = d
    def __repr__(self):
        """Represent.
        """
        io = StringIO.StringIO()
        items = self.dict.items()
        items.sort() # sort according to attribute name
        io.write('{ ')
        for k, v in items:
            io.write(repr(k))
            io.write(": ")
            io.write(repr(v))
            io.write(",\n\t\t")
        io.write('} ')
        return io.getvalue()

class SourceHash:
    """pretty-printed observable.Hash for source persistence.
    """
    def __init__(self,hash):
        """Initialize.
        """
        self.hash=hash
    def __repr__(self):
        """Represent.
        """
        return "observable.Hash(%s)"%repr(sanitizeDict(self.hash.properties))

class SourceThing:
    """pretty-printed Thing reference for source persistence.
    """
    def __init__(self,th):
        """Initialize.
        """
        self.thing=th
    def __repr__(self):
        """Represent.
        """
        return "t(%s)"%repr(self.thing.name)
