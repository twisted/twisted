
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
*Real* reloading support for Python.
"""

# System Imports
import sys
import types
import time
import linecache

# Sibling Imports
import log

lastRebuild = time.time()

class Sensitive:

    """A utility mixin that's sensitive to rebuilds.

    This is a mixin for classes (usually those which represent collections of
    callbacks) to make sure that their code is up-to-date before running.
    """

    lastRebuild = lastRebuild

    def needRebuildUpdate(self):
        yn = (self.lastRebuild < lastRebuild)
        return yn

    def rebuildUpToDate(self):
        self.lastRebuild = time.time()

    def latestVersionOf(self, object):
        """Get the latest version of an object.

        This can handle just about anything callable; instances, functions,
        methods, and classes.
        """
        t = type(object)
        if t == types.FunctionType:
            return latestFunction(object)
        elif t == types.MethodType:
            if object.im_self is None:
                return getattr(object.im_class, object.__name__)
            else:
                return getattr(object.im_self, object.__name__)
        elif t == types.InstanceType:
            # Kick it, if it's out of date.
            getattr(object, 'nothing', None)
            return object
        elif t == types.ClassType:
            return latestClass(object)
        else:
            print 'warning returning object!'
            return object

_modDictIDMap = {}

def latestFunction(oldFunc):
    """Get the latest version of a function.
    """
    # This may be CPython specific, since I believe jython instantiates a new
    # module upon reload.
    dictID = id(oldFunc.func_globals)
    module = _modDictIDMap.get(dictID)
    if module is None:
        return oldFunc
    return getattr(module, oldFunc.__name__)

def latestClass(oldClass):
    """Get the latest version of a class.
    """
    module = __import__(oldClass.__module__, {}, {}, 'nothing')
    newClass = getattr(module, oldClass.__name__)
    newBases = []
    for base in newClass.__bases__:
        newBases.append(latestClass(base))
    newClass.__bases__ = tuple(newBases)
    return newClass

def updateInstance(self):
    """Updates an instance to be current
    """
    self.__class__ = latestClass(self.__class__)

def __getattr__(self, name):
    """A getattr method to cause a class to be refreshed.
    """
    updateInstance(self)
    log.msg("(rebuilding stale %s instance (%s))" % (str(self.__class__), name))
    result = getattr(self, name)
    return result

def rebuild(module, doLog=1):
    """Reload a module and do as much as possible to replace its references.
    """
    global lastRebuild
    lastRebuild = time.time()
    if hasattr(module, 'ALLOW_TWISTED_REBUILD'):
        # Is this module allowed to be rebuilt?
        if not module.ALLOW_TWISTED_REBUILD:
            raise RuntimeError, "I am not allowed to be rebuilt."
    if doLog:
        log.msg( 'Rebuilding %s...' % str(module.__name__))
    d = module.__dict__
    _modDictIDMap[id(d)] = module
    classes = {}
    functions = {}
    values = {}
    if doLog:
        print '  (scanning %s): ' % str(module.__name__),
    for k, v in d.items():
        if type(v) == types.ClassType:
            # Failure condition -- instances of classes with buggy
            # __hash__/__cmp__ methods referenced at the module level...
            if v.__module__ == module.__name__:
                classes[v] = 1
                if doLog:
                    sys.stdout.write("c")
                    sys.stdout.flush()
        elif type(v) == types.FunctionType:
            if v.func_globals is module.__dict__:
                functions[v] = 1
                if doLog:
                    sys.stdout.write("f")
                    sys.stdout.flush()

    values.update(classes)
    values.update(functions)
    fromOldModule = values.has_key
    classes = classes.keys()
    functions = functions.keys()

    if doLog:
        print
        print '  (reload   %s)' % str(module.__name__)

    # Boom.
    reload(module)
    # Make sure that my traceback printing will at least be recent...
    linecache.clearcache()

    if doLog:
        print '  (cleaning %s): ' % str(module.__name__),

    for clazz in classes:
        if getattr(module, clazz.__name__) is clazz:
            print "WARNING: class %s not replaced by reload!" % str(clazz)
        else:
            if doLog:
                sys.stdout.write("x")
                sys.stdout.flush()
            clazz.__bases__ = ()
            clazz.__dict__.clear()
            clazz.__getattr__ = __getattr__
            clazz.__module__ = module.__name__
    if doLog:
        print
        print '  (fixing   %s): ' % str(module.__name__),
    modcount = 0
    for mk, mod in sys.modules.items():
        modcount = modcount + 1
        if mod == module or mod is None:
            continue

        if hasattr(mod, '__name__') and mod.__name__ != '__main__' and not hasattr(mod, '__file__'):
            # It's a builtin module; nothing to replace here.
            continue
        changed = 0
        for k, v in mod.__dict__.items():
            # print "checking for %s.%s" % (mod.__name__, k)
            try:
                hash(v)
            except TypeError:
                continue
            if fromOldModule(v):
                # print "Found a match! (%s.%s)" % (mod.__name__, k)
                if type(v) == types.ClassType:
                    if doLog:
                        sys.stdout.write("c")
                        sys.stdout.flush()
                    nv = latestClass(v)
                else:
                    if doLog:
                        sys.stdout.write("f")
                        sys.stdout.flush()
                    nv = latestFunction(v)
                changed = 1
                setattr(mod, k, nv)
            else:
                # Replace bases of non-module classes just to be sure.
                if type(v) == types.ClassType:
                    for base in v.__bases__:
                        if fromOldModule(base):
                            latestClass(v)
        if doLog and not changed and ((modcount % 10) ==0) :
            sys.stdout.write(".")
            sys.stdout.flush()
    if doLog:
        print
        print '   Rebuilt %s.' % str(module.__name__)
    return module
