"""
Cake is like eacher, but upside down and on fire. >:)
"""

import types
from cStringIO import StringIO

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
        
    def __repr__(self):
        return '<Cake _meth_=%r _args_=%r _kwargs_=%r>' % (self._meth_, self._args_, self._kwargs_)
        return object.__repr__(self)

    __str__ = __repr__

    def __getattr__(self, arg):
        return Cake(self, arg)

    def __call__(self, *args, **kwargs):
        return Cake(self, None, args, **kwargs)
        

class Yeast(object):
    def __init__(self, klassmethod, *args, **kwargs):
        self.ferment = curry(klassmethod, later, *args, **kwargs)

    def __get__(self, sugar, klass=None):
        if klass is None:
            return None
        return self.ferment(sugar)

def call_fmt(fn, args, kwargs):
    return (fn or '') + '(' + ', '.join(map(repr, args or ()) + [('%s=%r' % item) for item in (kwargs and kwargs.items() or ())]) + ')'

class Recipe(Cake):
    def __init__(self, cake):
        self.callstack = preheat(cake)

    def __call__(self, res):
        for fn, args, kwargs in self.callstack:
            if isinstance(fn, Recipe):
                res = fn(res)
            else:
                if fn == '__getitem__' and isinstance(res, list) and isinstance(args[0], types.SliceType):
                    res = res[args[0].start:args[0].stop]
                else:
                    _res = getattr(res, fn)(*args, **kwargs)
                    res = _res is None and res or _res
        return res

    def __repr__(self):
        return 'input.' + '.'.join([call_fmt(*tpl) for tpl in self.callstack])

    __str__ = __repr__
        
class Compiler:
    def __init__(self, recipe, indent = '    '):
        self.code = StringIO()
        self.recipe = recipe
        self.local_num = 0
        self.locals = {}
        self.locals_cache = {}
        self.indent = indent
    
    def newlocal(self, obj):
        if id(obj) in self.locals_cache:
            return self.locals_cache[id(obj)]
        name = 'local_' + str(self.local_num)
        self.local_num += 1
        self.locals_cache[id(obj)] = name
        self.locals[name] = obj
        return name

    def compile(self):
        for fn, args, kwargs in self.recipe.callstack:
            self.compile_step(fn, args, kwargs)
        self.writeln('return res')
        return self.code.getvalue(), self.locals

    def compile_step(self, fn, args, kwargs):
        if (fn[:2] == fn[-2:] == '__'):
            return getattr(self, 'handle_' + fn[2:-2], self.write_code)(fn, args, kwargs)
        return self.write_code(fn, args, kwargs)
    
    def writeln(self, s):
        self.code.write(self.indent + s + '\n')

    # optimize all you like here, isn't this really f'ing scary?

    def handle_getitem(self, fn, args, kwargs):
        if isinstance(args[0], types.SliceType):
            if args[0].step is None:
               name = self.newlocal(args[0])
               self.writeln('res = res[%s.start:%s.stop]' % (name, name))
               return 
        self.writeln('res = res[%s]' % self.newlocal(args[0]))

    def handle_add(self, fn, args, kwargs):
        self.writeln('res = res + %s' % self.newlocal(args[0]))

    def write_code(self, fn, args, kwargs):
        if not (args or kwargs):
            self.writeln('_res = res.%s()' % fn)
        elif not kwargs:
            self.writeln('_res = res.%s(*%s)' % (fn, self.newlocal(args)))
        elif not args:
            self.writeln('_res = res.%s(**%s)' % (fn, self.newlocal(kwargs)))
        else:
            self.writeln('_res = res.%s(*%s, **%s)' % (fn, self.newlocal(args), self.newlocal(kwargs)))
        self.writeln('res = _res is None and res or _res')

def code_recipe(recipe, indent=''):
    return Compiler(recipe, indent).compile()

def compile_recipe(recipe):
    if not isinstance(recipe, Recipe):
        recipe = Recipe(recipe)
    res = []
    codestring, locals = code_recipe(recipe, indent='    ')
    locals['callback'] = res.append
    codeobject = compile('def bake(res):\n' + codestring + 'callback(bake)', '<almost-baked cake>', 'exec')
    eval(codeobject, locals, globals())
    return res[0]

def preheat(cake):
    stack = []
    while cake is not None:
        stack.append(cake)
        cake = cake._prevcake_
    callstack = []
    while stack:
        cake = stack.pop()
        if isinstance(cake, Recipe):
            callstack.append((cake, None, None))
            continue
        if cake._args_ is not None:
            prevcake = cake
            while prevcake._meth_ is None:
                prevcake = prevcake._prevcake_
            callstack.append((prevcake._meth_, cake._args_, cake._kwargs_))
    return callstack
 
def bake(recipe, res):
    if not isinstance(recipe, Recipe):
        recipe = Recipe(recipe)
    return recipe(res)

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
    cake5 = Recipe(cake4)
    print cake5
    cake6 = (cake5 + [12, 13, 14]).sort().pop()
    for x in (cake6, cake5, cake4, cake3, cake2, cake1):
        print bake(x, [60])
    cakes = [x + 10 for x in map(cake + 1, [1, 2, 3, 4])]
    print map(curry(bake, later, 4), cakes)
    print code_recipe(cake5)[0].strip()
    fn = compile_recipe(cake5)
    fn2 = compile_recipe(cake4)
    print fn([60])
    print fn2([60])
    print fn([12, 100, 40, 1, 2, 3, 4, 5, 6, 9, 7, 10, 10.1, 10.2, 10.3, 11, 12, 13, 14])
