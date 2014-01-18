# -*- test-case-name: twisted.persisted.test.test_styles -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Different styles of persisted objects.
"""
from __future__ import print_function,division,absolute_import
from twisted.python.compat import _PY3,NativeStringIO

# System Imports
import types

if not _PY3:
    import copy_reg
else:
    import copyreg as copy_reg

import copy
import inspect
import sys

# Twisted Imports
from twisted.python import log
from twisted.python._reflectpy3 import qual, namedAny

oldModules = {}

## First, let's register support for some stuff that really ought to
## be registerable...

def pickleMethod(method):
    'support function for copy_reg to pickle method refs'
    return unpickleMethod, (method.im_func.__name__,
                             method.im_self,
                             method.im_class)

def unpickleMethod(im_name,
                    im_self,
                    im_class):
    'support function for copy_reg to unpickle method refs'
    try:
        unbound = getattr(im_class,im_name)
        if im_self is None:
            return unbound
        bound = types.MethodType(unbound.__func__, im_self, im_class)
        return bound
    except AttributeError:
        log.msg("Method",im_name,"not on class",im_class)
        assert im_self is not None,"No recourse: no instance to guess from."
        # Attempt a common fix before bailing -- if classes have
        # changed around since we pickled this method, we may still be
        # able to get it by looking on the instance's current class.
        unbound = getattr(im_self.__class__,im_name)
        log.msg("Attempting fixup with",unbound)
        if im_self is None:
            return unbound
        bound = types.MethodType(unbound.im_func, im_self, im_self.__class__)
        return bound

copy_reg.pickle(types.MethodType,
                pickleMethod,
                unpickleMethod)

def pickleModule(module):
    'support function for copy_reg to pickle module refs'
    return unpickleModule, (module.__name__,)

def unpickleModule(name):
    'support function for copy_reg to unpickle module refs'
    if name in oldModules:
        log.msg("Module has moved: %s" % name)
        name = oldModules[name]
        log.msg(name)
    return __import__(name,{},{},'x')


copy_reg.pickle(types.ModuleType,
                pickleModule,
                unpickleModule)

def pickleStringO(stringo):
    'support function for copy_reg to pickle StringIO.OutputTypes'
    return unpickleStringO, (stringo.getvalue(), stringo.tell())

def unpickleStringO(val, sek):
    x = NativeStringIO()
    x.write(val)
    x.seek(sek)
    return x

if hasattr(NativeStringIO, 'OutputType'):
    copy_reg.pickle(NativeStringIO.OutputType,
                    pickleStringO,
                    unpickleStringO)

def pickleStringI(stringi):
    return unpickleStringI, (stringi.getvalue(), stringi.tell())

def unpickleStringI(val, sek):
    x = NativeStringIO(val)
    x.seek(sek)
    return x


if hasattr(NativeStringIO, 'InputType'):
    copy_reg.pickle(NativeStringIO.InputType,
                pickleStringI,
                unpickleStringI)



class Ephemeral:
    """
    This type of object is never persisted; if possible, even references to it
    are eliminated.
    """
    def _warn(self):
        log.msg( "WARNING: serializing ephemeral %s" % self )
        import gc
        if '__pypy__' not in sys.builtin_module_names:
            if getattr(gc, 'get_referrers', None):
                for r in gc.get_referrers(self):
                    log.msg( " referred to by %s" % (r,))


    # This seems to work on Python 3.
    def __reduce__(self):
        self._warn()
        return _loadEphemeral, (qual(self.__class__),)


    # This is still needed for Python 2.
    def __getstate__(self):
        self._warn()
        return None


    def __setstate__(self, state):
        _loadEphemeral(qual(self.__class__))
        self.__class__ = Ephemeral



def _loadEphemeral(name):
    """
    Issue a log event warning about an Ephemeral being unserialized.
    """
    log.msg( "WARNING: unserializing ephemeral %s" % (name,))
    return Ephemeral()



versionedsToUpgrade = {}
upgraded = {}

def doUpgrade():
    global versionedsToUpgrade, upgraded
    for versioned in list(versionedsToUpgrade.values()):
        requireUpgrade(versioned)
    versionedsToUpgrade = {}
    upgraded = {}

def requireUpgrade(obj):
    """Require that a Versioned instance be upgraded completely first.
    """
    objID = id(obj)
    if objID in versionedsToUpgrade and objID not in upgraded:
        upgraded[objID] = 1
        obj.versionUpgrade()
        return obj

def _aybabtu(c):
    """
    Get all of the parent classes of C{c}, not including C{c} itself, which are
    strict subclasses of L{Versioned}.

    The name comes from "all your base are belong to us", from the deprecated
    L{twisted.python.reflect.allYourBase} function.

    @param c: a class
    @returns: list of classes
    """
    # begin with two classes that should *not* be included in the
    # final result
    l = [c, Versioned]
    for b in inspect.getmro(c):
        if b not in l and issubclass(b, Versioned):
            l.append(b)
    # return all except the unwanted classes
    return l[2:]


def _loadVersioned(className, state):
    print('HOOOOOOOO')
    cls = namedAny(className)
    self = cls.__new__(cls)
    self.__setstate__(state)
    return self



class Versioned:
    """
    This type of object is persisted with versioning information.

    I have a single class attribute, the int persistenceVersion.  After I am
    unserialized (and styles.doUpgrade() is called), self.upgradeToVersionX()
    will be called for each version upgrade I must undergo.

    For example, if I serialize an instance of a Foo(Versioned) at version 4
    and then unserialize it when the code is at version 9, the calls::

      self.upgradeToVersion5()
      self.upgradeToVersion6()
      self.upgradeToVersion7()
      self.upgradeToVersion8()
      self.upgradeToVersion9()

    will be made.  If any of these methods are undefined, a warning message
    will be printed.
    """
    persistenceVersion = 0
    persistenceForgets = ()

    # This doesn't help in the "null upgrade" case on Python 3 because it's
    # some other class that gets serialized.  And on Python 3 that also means
    # __setstate__ apparently never gets called even after the class switches
    # to Versioned.
    def __reduce__(self):
        return _loadVersioned, (qual(self.__class__), self.__getstate__())


    # Python 2.
    def __setstate__(self, state):
        versionedsToUpgrade[id(self)] = self
        self.__dict__ = state


    def __getstate__(self, dict=None):
        """Get state, adding a version number to it on its way out.
        """
        dct = copy.copy(dict or self.__dict__)
        bases = _aybabtu(self.__class__)
        bases.reverse()
        bases.append(self.__class__) # don't forget me!!
        for base in bases:
            if 'persistenceForgets' in base.__dict__:
                for slot in base.persistenceForgets:
                    if slot in dct:
                        del dct[slot]
            if 'persistenceVersion' in base.__dict__:
                dct['%s.persistenceVersion' % qual(base)] = base.persistenceVersion
        return dct


    def versionUpgrade(self):
        """(internal) Do a version upgrade.
        """
        bases = _aybabtu(self.__class__)
        # put the bases in order so superclasses' persistenceVersion methods
        # will be called first.
        bases.reverse()
        bases.append(self.__class__) # don't forget me!!
        # first let's look for old-skool versioned's
        if "persistenceVersion" in self.__dict__:

            # Hacky heuristic: if more than one class subclasses Versioned,
            # we'll assume that the higher version number wins for the older
            # class, so we'll consider the attribute the version of the older
            # class.  There are obviously possibly times when this will
            # eventually be an incorrect assumption, but hopefully old-school
            # persistenceVersion stuff won't make it that far into multiple
            # classes inheriting from Versioned.

            pver = self.__dict__['persistenceVersion']
            del self.__dict__['persistenceVersion']
            highestVersion = 0
            highestBase = None
            for base in bases:
                if not base.__dict__.has_key('persistenceVersion'):
                    continue
                if base.persistenceVersion > highestVersion:
                    highestBase = base
                    highestVersion = base.persistenceVersion
            if highestBase:
                self.__dict__['%s.persistenceVersion' % qual(highestBase)] = pver
        for base in bases:
            # ugly hack, but it's what the user expects, really
            if (Versioned not in base.__bases__ and
                'persistenceVersion' not in base.__dict__):
                continue
            currentVers = base.persistenceVersion
            pverName = '%s.persistenceVersion' % qual(base)
            persistVers = (self.__dict__.get(pverName) or 0)
            if persistVers:
                del self.__dict__[pverName]
            assert persistVers <=  currentVers, "Sorry, can't go backwards in time."
            while persistVers < currentVers:
                persistVers = persistVers + 1
                method = base.__dict__.get('upgradeToVersion%s' % persistVers, None)
                if method:
                    log.msg( "Upgrading %s (of %s @ %s) to version %s" % (qual(base), qual(self.__class__), id(self), persistVers) )
                    method(self)
                else:
                    log.msg( 'Warning: cannot upgrade %s to version %s' % (base, persistVers) )
