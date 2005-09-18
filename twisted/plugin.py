# -*- test-case-name: twisted.test.test_plugin -*-
# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

"""
Plugin system for Twisted.

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
@author: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

from __future__ import generators

import os, errno

from zope.interface import Interface, providedBy

try:
    import cPickle as pickle
except ImportError:
    import pickle

from twisted.python.components import getAdapterFactory
from twisted.python.reflect import namedAny
from twisted.python import log

try:
    from os import stat_float_times
    from os.path import getmtime as _getmtime
    def getmtime(x):
        sft = stat_float_times()
        stat_float_times(True)
        try:
            return _getmtime(x)
        finally:
            stat_float_times(sft)
except:
    from os.path import getmtime

class IPlugin(Interface):
    """Interface that must be implemented by all plugins.

    Only objects which implement this interface will be considered for
    return by C{getPlugins}.  To be useful, plugins should also
    implement some other application-specific interface.
    """

class ITestPlugin(Interface):
    """A plugin for use by the plugin system's unit tests.

    Do not use this.
    """

class ITestPlugin2(Interface):
    """See L{ITestPlugin}.
    """

class CachedPlugin(object):
    def __init__(self, dropin, name, description, provided):
        self.dropin = dropin
        self.name = name
        self.description = description
        self.provided = provided
        self.dropin.plugins.append(self)

    def __repr__(self):
        return '<CachedPlugin %r/%r (provides %r)>' % (
            self.name, self.dropin.moduleName,
            ', '.join([i.__name__ for i in self.provided]))

    def load(self):
        return namedAny(self.dropin.moduleName + '.' + self.name)

    def __conform__(self, interface, registry=None, default=None):
        for providedInterface in self.provided:
            if providedInterface.isOrExtends(interface):
                return self.load()
            if getAdapterFactory(providedInterface, interface, None) is not None:
                return interface(self.load(), default)
        return default

    # backwards compat HOORJ
    getComponent = __conform__

class CachedDropin(object):
    def __init__(self, moduleName, description):
        self.moduleName = moduleName
        self.description = description
        self.plugins = []

def _generateCacheEntry(provider):
    dropin = CachedDropin(provider.__name__,
                          provider.__doc__)
    for k, v in provider.__dict__.iteritems():
        plugin = IPlugin(v, None)
        if plugin is not None:
            cachedPlugin = CachedPlugin(dropin, k, v.__doc__, list(providedBy(plugin)))
    return dropin

try:
    fromkeys = dict.fromkeys
except AttributeError:
    def fromkeys(keys, value=None):
        d = {}
        for k in keys:
            d[k] = value
        return d

_exts = fromkeys(['.py', '.so', '.pyd', '.dll'])

try:
    WindowsError
except NameError:
    class WindowsError:
        """
        Stand-in for sometimes-builtin exception on platforms for which it
        is missing.
        """

# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/debug/base/system_error_codes.asp
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_NAME = 123

def getCache(module):
    topcache = {}
    for p in module.__path__:
        dropcache = os.path.join(p, "dropin.cache")
        try:
            cache = pickle.load(file(dropcache))
            lastCached = getmtime(dropcache)
            dirtyCache = False
        except:
            cache = {}
            lastCached = 0
            dirtyCache = True
        try:
            dropinNames = os.listdir(p)
        except WindowsError, e:
            if e.errno == ERROR_PATH_NOT_FOUND:
                continue
            elif e.errno == ERROR_INVALID_NAME:
                log.msg("Invalid path %r in search path for %s" % (p, module.__name__))
                continue
            else:
                raise
        except OSError, ose:
            if ose.errno not in (errno.ENOENT, errno.ENOTDIR):
                raise
            else:
                continue
        else:
            pys = {}
            for dropinName in dropinNames:
                moduleName, moduleExt = os.path.splitext(dropinName)
                if moduleName != '__init__' and moduleExt in _exts:
                    pyFile = os.path.join(p, dropinName)
                    try:
                        pys[moduleName] = getmtime(pyFile)
                    except:
                        log.err()

        for moduleName, lastChanged in pys.iteritems():
            if lastChanged >= lastCached or moduleName not in cache:
                dirtyCache = True
                try:
                    provider = namedAny(module.__name__ + '.' + moduleName)
                except:
                    log.err()
                else:
                    entry = _generateCacheEntry(provider)
                    cache[moduleName] = entry

        topcache.update(cache)

        if dirtyCache:
            newCacheData = pickle.dumps(cache, 2)
            tmpCacheFile = dropcache + ".new"
            try:
                stage = 'opening'
                f = file(tmpCacheFile, 'wb')
                stage = 'writing'
                f.write(newCacheData)
                stage = 'closing'
                f.close()
                stage = 'renaming'
                os.rename(tmpCacheFile, dropcache)
            except (OSError, IOError), e:
                # A large number of errors can occur here.  There's nothing we
                # can really do about any of them, but they are also non-fatal
                # (they only slow us down by preventing results from being
                # cached).  Notify the user of the error, but proceed as if it
                # had not occurred.
                log.msg("Error %s plugin cache file %r (%r): %r" % (
                    stage, tmpCacheFile, dropcache, os.strerror(e.errno)))

    return topcache

import twisted.plugins
def getPlugins(interface, package=twisted.plugins):
    """Retrieve all plugins implementing the given interface beneath the given module.

    @param interface: An interface class.  Only plugins which
    implement this interface will be returned.

    @param package: A package beneath which plugins are installed.  For
    most uses, the default value is correct.

    @return: An iterator of plugins.
    """
    allDropins = getCache(package)
    for dropin in allDropins.itervalues():
        for plugin in dropin.plugins:
            try:
                adapted = interface(plugin, None)
            except:
                log.err()
            else:
                if adapted is not None:
                    yield adapted

                    
# Old, backwards compatible name.  Don't use this.
getPlugIns = getPlugins


__all__ = ['getPlugins']
