class InterfaceProxy:
    """A wrapper to put around an object that only allows access to the
    specified interfaces.
    """
    def __init__(self, original, interfaces=None):
        import zope
        if interfaces is None:
            interfaces = zope.interface.providedBy(original)
        for interface in interfaces:
            for name in interface.names():
                attr = interface[name]
                if zope.interface.interfaces.IMethod.providedBy(attr):
                    setattr(self, name,  _functionWrapper(original, name,
                                                         attr.getSignatureInfo()))
                else:
                    raise TypeError("Cannot handle non-function attributes yet")


def _functionWrapper(original, name, signatureInfo):
    positional=signatureInfo['positional']
    kwargs=signatureInfo['kwargs']
    required=signatureInfo['required']
    optional=signatureInfo['optional']
    varargs=signatureInfo['varargs']
    
    def _callthrough(*pos, **kw):
        argcount = len(pos)
        kwcount = len(kw)
        if len(positional) > 0 and positional[0] == 'self':
            # FIXME, hack.
            # 'self' shouldn't be in the interface declarations, but is.
            argcount=argcount+1
        
        if len(positional) > 0 or kwargs is not None or varargs is not None:
            if varargs is None and argcount > len(positional):
                raise TypeError("%.200s() takes %s %d %sargument%s (%d given)" %(
                    name,
                    len(optional) and "at most" or "exactly",
                    len(positional),
                    kwcount and "non-keyword " or "",
                    len(positional) != 1 and "s" or "",
                    argcount))
            for k in kw:
                if kwargs is None:
                    if k not in kwargs:
                        raise TypeError("%.200s() got an unexpected "
                                        "keyword argument '%.400s'" %(
                            name, k))
                for n in positional[:arglen]:
                    if n == k:
                        raise TypeError("%.200s() got multiple values for "
                                        "keyword argument '%.400s'" %(
                            name, k))
            for i in range(argcount, len(required)):
                n = required[i]
                if not kw.has_key(n):
                    raise TypeError("%.200s() takes %s %d %sargument%s (%d given)" %(
                        name, 
                        (varargs is not None or optional) and "at least" or "exactly",
                        len(required), kwcount and "non-keyword" or "",
                        len(required) != 1 and "s" or "", i))
        else:
            if argcount > 0 or kwcount > 0:
                raise TypeError("%.200s() takes no arguments (%d given)" % (
                    name, argcount+kwcount))
        
        return getattr(original, name)(*pos, **kw)
    return _callthrough

