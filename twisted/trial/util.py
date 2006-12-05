# -*- test-case-name: twisted.trial.test.test_util -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""A collection of utility functions and classes, used internally by Trial.

API Stability: Unstable

This code is for Trial's internal use.  Do NOT use this code if you are writing
tests.  It is subject to change at the Trial maintainer's whim.  There is
nothing here in this module for you to use unless you are maintaining Trial.

Any non-Trial Twisted code that uses this module will be shot.

Maintainer: U{Jonathan Lange<mailto:jml@twistedmatrix.com>}
"""


from __future__ import generators

import traceback, gc, sys
from twisted.python import log, threadpool
from twisted.internet import interfaces, utils

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']

# ---------------------------------

DEFAULT_TIMEOUT = object()
DEFAULT_TIMEOUT_DURATION = 120.0


class FailureError(Exception):
    """Wraps around a Failure so it can get re-raised as an Exception"""

    def __init__(self, failure):
        Exception.__init__(self)
        self.original = failure


class DirtyReactorError(Exception):
    """emitted when the reactor has been left in an unclean state"""

class DirtyReactorWarning(Warning):
    """emitted when the reactor has been left in an unclean state"""

class PendingTimedCallsError(Exception):
    """raised when timed calls are left in the reactor"""

DIRTY_REACTOR_MSG = "THIS WILL BECOME AN ERROR SOON! reactor left in unclean state, the following Selectables were left over: "
PENDING_TIMED_CALLS_MSG = "pendingTimedCalls still pending (consider setting twisted.internet.base.DelayedCall.debug = True):"


class _Janitor(object):
    logErrCheck = True
    cleanPending = cleanThreads = cleanReactor = True

    def postCaseCleanup(self):
        return self._dispatch('cleanPending')

    def postClassCleanup(self):
        return self._dispatch('cleanReactor',
                              'cleanPending', 'cleanThreads')

    def _dispatch(self, *attrs):
        for attr in attrs:
            getattr(self, "do_%s" % attr)()

    def do_cleanPending(cls):
        # don't import reactor when module is loaded
        from twisted.internet import reactor

        # flush short-range timers
        reactor.iterate(0)
        reactor.iterate(0)

        pending = reactor.getDelayedCalls()
        if pending:
            s = PENDING_TIMED_CALLS_MSG
            for p in pending:
                s += " %s\n" % (p,)
                if p.active():
                    p.cancel() # delete the rest
                else:
                    print "WEIRNESS! pending timed call not active+!"
            raise PendingTimedCallsError(s)
    do_cleanPending = utils.suppressWarnings(
        do_cleanPending, (('ignore',), {'category': DeprecationWarning,
                                        'message':
                                        r'reactor\.iterate cannot be used.*'}))
    do_cleanPending = classmethod(do_cleanPending)


    def do_cleanThreads(cls):
        from twisted.internet import reactor
        if interfaces.IReactorThreads.providedBy(reactor):
            reactor.suggestThreadPoolSize(0)
            if hasattr(reactor, 'threadpool') and reactor.threadpool:
                reactor.threadpool.stop()
                reactor.threadpool = None
                # *Put it back* and *start it up again*.  The
                # reactor's threadpool is *private*: we cannot just
                # rape it and walk away.
                reactor.threadpool = threadpool.ThreadPool(0, 10)
                reactor.threadpool.start()


    do_cleanThreads = classmethod(do_cleanThreads)

    def do_cleanReactor(cls):
        s = []
        from twisted.internet import reactor
        removedSelectables = reactor.removeAll()
        if removedSelectables:
            s.append(DIRTY_REACTOR_MSG)
            for sel in removedSelectables:
                if interfaces.IProcessTransport.providedBy(sel):
                    sel.signalProcess('KILL')
                s.append(repr(sel))
        if s:
            raise DirtyReactorError(' '.join(s))
    do_cleanReactor = classmethod(do_cleanReactor)

    def doGcCollect(cls):
         gc.collect()


def suppress(action='ignore', **kwarg):
    """sets up the .suppress tuple properly, pass options to this method
    as you would the stdlib warnings.filterwarnings()

    so to use this with a .suppress magic attribute you would do the
    following:

      >>> from twisted.trial import unittest, util
      >>> import warnings
      >>>
      >>> class TestFoo(unittest.TestCase):
      ...     def testFooBar(self):
      ...         warnings.warn("i am deprecated", DeprecationWarning)
      ...     testFooBar.suppress = [util.suppress(message='i am deprecated')]
      ...
      >>>

    note that as with the todo and timeout attributes: the module level
    attribute acts as a default for the class attribute which acts as a default
    for the method attribute. The suppress attribute can be overridden at any
    level by specifying .suppress = []
    """
    return ((action,), kwarg)


def profiled(f, outputFile):
    def _(*args, **kwargs):
        if sys.version_info[0:2] != (2, 4):
            import profile
            prof = profile.Profile()
            try:
                result = prof.runcall(f, *args, **kwargs)
                prof.dump_stats(outputFile)
            except SystemExit:
                pass
            prof.print_stats()
            return result
        else: # use hotshot, profile is broken in 2.4
            import hotshot.stats
            prof = hotshot.Profile(outputFile)
            try:
                return prof.runcall(f, *args, **kwargs)
            finally:
                stats = hotshot.stats.load(outputFile)
                stats.strip_dirs()
                stats.sort_stats('cum')   # 'time'
                stats.print_stats(100)
    return _


def getPythonContainers(meth):
    """Walk up the Python tree from method 'meth', finding its class, its module
    and all containing packages."""
    containers = []
    containers.append(meth.im_class)
    moduleName = meth.im_class.__module__
    while moduleName is not None:
        module = sys.modules.get(moduleName, None)
        if module is None:
            module = __import__(moduleName)
        containers.append(module)
        moduleName = getattr(module, '__module__', None)
    return containers


_DEFAULT = object()
def acquireAttribute(objects, attr, default=_DEFAULT):
    """Go through the list 'objects' sequentially until we find one which has
    attribute 'attr', then return the value of that attribute.  If not found,
    return 'default' if set, otherwise, raise AttributeError. """
    for obj in objects:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    if default is not _DEFAULT:
        return default
    raise AttributeError('attribute %r not found in %r' % (attr, objects))


def findObject(name):
    """Get a fully-named package, module, module-global object or attribute.
    Forked from twisted.python.reflect.namedAny.

    Returns a tuple of (bool, obj).  If bool is True, the named object exists
    and is returned as obj.  If bool is False, the named object does not exist
    and the value of obj is unspecified.
    """
    names = name.split('.')
    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        trialname = '.'.join(moduleNames)
        if len(trialname) == 0:
            return (False, None)
        try:
            topLevelPackage = __import__(trialname)
        except ImportError:
            # if the ImportError happened in the module being imported,
            # this is a failure that should be handed to our caller.
            # count stack frames to tell the difference.
            exc_info = sys.exc_info()
            if len(traceback.extract_tb(exc_info[2])) > 1:
                try:
                    # Clean up garbage left in sys.modules.
                    del sys.modules[trialname]
                except KeyError:
                    # Python 2.4 has fixed this.  Yay!
                    pass
                raise exc_info[0], exc_info[1], exc_info[2]
            moduleNames.pop()
    obj = topLevelPackage
    for n in names[1:]:
        try:
            obj = getattr(obj, n)
        except AttributeError:
            return (False, obj)
    return (True, obj)


__all__ = ['FailureError', 'DirtyReactorWarning', 'DirtyReactorError',
           'PendingTimedCallsError']
