"""
Cake is like eacher, but upside down and on fire. >:)
"""

class _later:
    pass
later = _later()

def curry(fn, *args, **kwargs):
    if later not in args:
        def curried(*_args, **_kwargs):
            d = kwargs.copy()
            d.update(_kwargs)
            return fn(*(args+_args), **d)
    else:
        def curried(*_args, **_kwargs):
            d = kwargs.copy()
            d.update(_kwargs)
            nargs, _args = list(args), list(_args)
            for x in xrange(len(nargs)):
                if nargs[x] is later:
                    nargs[x] = _args.pop(0)
            while _args:
                nargs.append(_args.pop(0))
            return fn(*tuple(nargs), **d)
    return curried

class Cake(object):
    _prevcake_ = None
    _meth_ = None
    _args_ = None
    _kwargs_ = None
    def __init__(self, *args, **kwargs):
        if len(args) == 0:
            pass
        elif len(args) == 2:
            self._prevcake_, self._meth_ = args
        else:
            self._prevcake_, self._meth_, self._args_ = args
            self._kwargs_ = kwargs
        #print 'new cake: %r %r %r' % (self, args, kwargs)
        
    def __repr__(self):
        return '<Cake _meth_=%r _args_=%r _kwargs_=%r>' % (self._meth_, self._args_, self._kwargs_)
        return object.__repr__(self)

    def __getattr__(self, arg):
        return Cake(self, arg)

    def __call__(self, *args, **kwargs):
        return Cake(self, None, args, **kwargs)
        

class Yeast(object):
    def __init__(self, klassmethod, *args, **kwargs):
        self.ferment = curry(klassmethod, later, *args, **kwargs)

    def __get__(self, sugar, klass=None):
        if not klass:
            return None
        return self.ferment(sugar)

def bake(cake, res):
    stack = []
    while cake is not None:
        stack.append(cake)
        cake = cake._prevcake_
    
    while stack:
        cake = stack.pop()
        #print repr(cake)
        if cake._args_ is not None:
            prevcake = cake
            while prevcake._meth_ is None:
                prevcake = prevcake._prevcake_
            #print prevcake._meth_, cake._args_, cake._kwargs_
            _res = getattr(res, prevcake._meth_)(*cake._args_, **cake._kwargs_)
            #print res, _res
            res = _res is None and res or _res
    return res

_SPECIALS = """
    __hash__
    __len__ __getitem__ __setitem__ __delitem__ __iter__ __contains__
    __add__ __sub__ __mul__ __floordiv__ __mod__ __divmod__ __pow__
    __lshift__ __rshift__ __and__ __xor__ __or__ __div__ __truediv__
    __radd__ __rsub__ __rmul__ __rdiv__ __rtruediv__ __rfloordiv__
    __rmod__ __rdivmod__ __rpow__ __rlshift__ __rrshift__ __rand__
    __rxor__ __ror__ __iadd__ __isub__ __imul__ __idiv__ __itruediv__
    __ifloordiv__ __imod__ __ipow__ __ilshift__ __irshift__ __iand__
    __ixor__ __ior__ __neg__ __pos__ __abs__ __invert__ 
    __lt__ __le__ __eq__ __ne__ __gt__ __ge__ __cmp__ __nonzero__
    __complex__ __int__ __long__ __float__ __oct__ __hex__ __coerce__
    """.split()

#_EXCLUDEDSPECIALS = """__getattr__ __setattr__ __delattr__ __repr__ __str__ __call__""".split()

def _makeClassSpecial(klass):
    for meth in [_m for _m in _SPECIALS]:
        setattr(klass, meth, Yeast(klass.__getattr__, meth))
_makeClassSpecial(Cake)

if __name__=='__main__':
    cake = Cake()
    cake1 = cake.append(12)
    cake2 = cake1 + [1, 2, 3]
    cake3 = cake2.sort()
    cake4 = cake3[2:4]
    for x in (cake1, cake2, cake3, cake4):
        print bake(x, [60])
    cakes = [x + 10 for x in map(cake + 1, [1, 2, 3, 4])]
    print map(curry(bake, later, 4), cakes)
