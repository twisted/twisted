"""Some stuff to support the Decorator pattern"""

class DirectWrap(object):
    def __init__(self, func, wrapper):
        self.func = func
        self.wrapper = wrapper
    def __call__(self, *args, **kwargs):
        return self.wrapper(self.func(*args, **kwargs))

class IndirectWrap(object):
    def __init__(self, func, wrapper):
        self.func = func
        self.wrapper = wrapper
    def __call__(self, *args, **kwargs):
        return self.wrapper(self.func, *args, **kwargs)

class Decorator(object):
    def __init__(self, target, factoryMethods=[]):
        self.target = target
        self.factoryMethods = factoryMethods
    def __getattr__(self, name):
        attr = getattr(self.target, name)
        if name in self.factoryMethods:
            attr = DirectWrap(attr, self._decorate)
        return attr
    def _decorate(self, target):
        return self.__class__(target, self.factoryMethods)

class CommonWrapperDecorator(Decorator):
    def __init__(self, target, factoryMethods=[],
        wrapper=lambda x: x, wrappedMethods=[], wrapStyle=DirectWrap
    ):
        self.wrapper = wrapper
        self.wrappedMethods = wrappedMethods
        self.wrapStyle = wrapStyle
        Decorator.__init__(self, target, factoryMethods)
    def __getattr__(self, name):
        attr = Decorator.__getattr__(self, name)
        if name in self.wrappedMethods:
            attr = self.wrapStyle(attr, self.wrapper)
        return attr
    def _decorate(self, target):
        return self.__class__(target, self.factoryMethods,
            self.wrapper, self.wrappedMethods, self.wrapStyle)

def introspectMethods(target, respectPrivate=True, exceptMethods=[]):
    ret = []
    for name in dir(target):
        attr = getattr(target, name)
        if callable(attr):
            if not respectPrivate or not name.startswith("_"):
                if name not in exceptMethods:
                    ret.append(name)
    return ret
            
