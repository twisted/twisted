"""
This module lets you wrap up modules with an access protection layer which
prevents access to names not declared in __all__.

It will allows access to private names from code in the same package, but
not from code in other packages.

"""

# Evil hack? What evil hack!
import imp, inspect, types, sys, os

globalAllows = ['__version__', '__file__', '__path__']
justReport = True

class PrivateModule(types.ModuleType):
    """Our module wrapper which restricts access"""
    
    def __init__(self, original):
        types.ModuleType.__init__(self, original.__name__)
        self.__dict__['__private__'] = original
        
    def allowPrivate(self, name, callframe):
        """Is this caller allowed access to the private fields of my module?"""
        caller_module = callframe.f_globals.get('__name__', '')
        my_module = self.__private__.__name__
        if justReport:
            sys.stderr.write("<= private %s.%s from %s (%s): " % (my_module, name, caller_module, callframe.f_code.co_name))

        if caller_module == my_module:
            sys.stderr.write("=> Yes\n")
            return True
        
        caller_parts = caller_module.split('.')
        my_parts = my_module.split('.')
        if len(caller_parts) == 1:
            sys.stderr.write("=> No\n")
            return False

        if caller_parts[:-1] == my_parts[:-1]:
            sys.stderr.write("=> Yes\n")
            return True
        sys.stderr.write("=> No\n")
        return False
        
    def __getattr__(self, name):
        if not (name in getattr(self.__private__, '__all__', ()) or
                name in globalAllows or
                self.allowPrivate(name, inspect.currentframe().f_back)):
            if not justReport:
                raise AttributeError("%r module attribute %r is private (not in __all__)." %
                                     (self.__private__.__name__, name))
        return getattr(self.__private__, name)
    
    def __setattr__(self, name, value):
        if not (name in getattr(self.__private__, '__all__', ()) or
                name in globalAllows or
                self.allowPrivate(name, inspect.currentframe().f_back)):
            if not justReport:
                raise AttributeError("%r module attribute %r is private (not in __all__)." %
                                     (self.__private__.__name__, name))
        return setattr(self.__private__, name, value)

prefixes=[]

def privatizeModule(name, m):
    """Decide whether to wrap this module or not, and then do it"""
    # sys.stderr.write("possibly privatizing %s\n"%name)
    if type(m) != PrivateModule and hasattr(m, '__all__'):
        for x in prefixes:
            if name.startswith(x):
                # sys.stderr.write("privatizing %r %r\n" % (name, type(sys.modules[name])))
                m = sys.modules[name] = PrivateModule(m)
                return m
    return m

class PrivatizeImporter:
    """An import hook which will cause all modules to be privatized (if requested), as they are loaded."""
    def __init__(self, path=None):
        if path is not None and not os.path.isdir(path):
            raise ImportError
        self.path = path

    def find_module(self, fullname, path=None):
        subname = fullname.split(".")[-1]
        if subname != fullname and self.path is None:
            return None
        if self.path is None:
            path = None
        else:
            path = [self.path]
        file, filename, stuff = imp.find_module(subname, path)
        return PrivatizeLoader(file, filename, stuff)

class PrivatizeLoader:
    def __init__(self, file, filename, stuff):
        self.file = file
        self.filename = filename
        self.stuff = stuff

    def load_module(self, fullname):
        mod = imp.load_module(fullname, self.file, self.filename, self.stuff)
        if self.file:
            self.file.close()
        # mod.__loader__ = self  # for introspection
        return privatizeModule(fullname, mod)

hookinstalled = False
def installImportHook():
    global hookinstalled
    if not hookinstalled:
        # This gets frozen and builtin modules
        sys.meta_path.insert(0, PrivatizeImporter())
        # This gets standard path-based modules
        sys.path_hooks.insert(0, PrivatizeImporter)
        hookinstalled = True

def privatizeModulesWithPrefix(prefix):
    installImportHook()
    prefixes.append(prefix)
    for name, m in sys.modules.iteritems():
        if m is not None:
            privatizeModule(name, m)

__all__ = ['privatizeModulesWithPrefix', 'justReport']

