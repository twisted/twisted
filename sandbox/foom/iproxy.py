from zope.interface import providedBy, Declaration, Interface, interfaces as zinterfaces
from twisted.python.reflect import getClass
from twisted.python import components

class IPrivate(Interface):
    """Allows access to private parts of an object"""
    
class InterfaceProxy:
    """A wrapper to put around an object that only allows access to the
    specified interfaces.
    """
    __inInit=1
    def __init__(self, original, interfaces=None):
        self.__original=original
        attrs=[]
        
        if interfaces is None:
            interfaces = providedBy(original)
        else:
            interfaces = Declaration(interfaces).flattened()
            
        for interface in interfaces:
            for name in interface.names():
                attr = interface[name]
                if zinterfaces.IMethod.providedBy(attr):
                    setattr(self, name,  _functionWrapper(original, name,
                                                         attr.getSignatureInfo()))
                elif zinterfaces.IAttribute.providedBy(attr):
                    attrs.append(name)
                else:
                    raise TypeError("Unknown kind of attribute.")
        self.__attrs=attrs
        self.__inInit=0
        
    def __getattr__(self, name):
        if name not in self.__attrs:
            raise AttributeError("'%s' object has no attribute '%s'" %(
                getClass(self.__original).__name__, name))
        return getattr(self.__original, name)
    
    def __setattr__(self, name, val):
        if self.__inInit:
            self.__dict__[name]=val
            return
        
        if name not in self.__attrs:
            raise AttributeError("'%s' object has no attribute '%s'" %(
                getClass(self.__original).__name__, name))
        return setattr(self.__original, name, val)

components.registerAdapter(lambda o: o.original, InterfaceProxy, IPrivate)

def _functionWrapper(original, name, signatureInfo):
    positional=signatureInfo['positional']
    required=signatureInfo['required']
    optional=signatureInfo['optional']
    hasvarargs=signatureInfo['varargs'] is not None
    haskwargs=signatureInfo['kwargs'] is not None

    def _callthrough(*pos, **kw):
        argcount = len(pos)
        kwcount = len(kw)
        
        if len(positional) > 0 or haskwargs or hasvarargs:
            if not hasvarargs and argcount > len(positional):
                raise TypeError("%.200s() takes %s %d %sargument%s (%d given)" %(
                    name,
                    len(optional) and "at most" or "exactly",
                    len(positional),
                    kwcount and "non-keyword " or "",
                    len(positional) != 1 and "s" or "",
                    argcount))
            for k in kw:
                if not haskwargs:
                    if k not in positional:
                        raise TypeError("%.200s() got an unexpected "
                                        "keyword argument '%.400s'" %(
                            name, k))
                for n in positional[:argcount]:
                    if n == k:
                        raise TypeError("%.200s() got multiple values for "
                                        "keyword argument '%.400s'" %(
                            name, k))
            for i in range(argcount, len(required)):
                n = required[i]
                if not kw.has_key(n):
                    raise TypeError("%.200s() takes %s %d %sargument%s (%d given)" %(
                        name, 
                        (hasvarargs or optional) and "at least" or "exactly",
                        len(required), kwcount and "non-keyword" or "",
                        len(required) != 1 and "s" or "", i))
        else:
            if argcount > 0 or kwcount > 0:
                raise TypeError("%.200s() takes no arguments (%d given)" % (
                    name, argcount+kwcount))
        
        return getattr(original, name)(*pos, **kw)
    return _callthrough

