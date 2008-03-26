# -*- test-case-name: twisted.trial.test.test_util -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
A collection of utility functions and classes, used internally by Trial.

This code is for Trial's internal use.  Do NOT use this code if you are writing
tests.  It is subject to change at the Trial maintainer's whim.  There is
nothing here in this module for you to use unless you are maintaining Trial.

Any non-Trial Twisted code that uses this module will be shot.

Maintainer: U{Jonathan Lange<mailto:jml@twistedmatrix.com>}
"""

import traceback, sys

from twisted.internet import defer, utils, interfaces
from twisted.python.failure import Failure


DEFAULT_TIMEOUT = object()
DEFAULT_TIMEOUT_DURATION = 120.0


class FailureError(Exception):
    """
    DEPRECATED in Twisted 8.0. This exception is never raised by Trial.

    Wraps around a Failure so it can get re-raised as an Exception.
    """

    def __init__(self, failure):
        Exception.__init__(self)
        self.original = failure



class DirtyReactorWarning(Warning):
    """
    DEPRECATED in Twisted 8.0.

    This warning is not used by Trial any more.
    """



class DirtyReactorError(Exception):
    """
    DEPRECATED in Twisted 8.0. This is not used by Trial any more.
    """

    def __init__(self, msg):
        Exception.__init__(self, self._getMessage(msg))

    def _getMessage(self, msg):
        return ("reactor left in unclean state, the following Selectables "
                "were left over: %s" % (msg,))




class PendingTimedCallsError(DirtyReactorError):
    """
    DEPRECATED in Twisted 8.0. This is not used by Trial any more.
    """

    def _getMessage(self, msg):
        return ("pendingTimedCalls still pending (consider setting "
                "twisted.internet.base.DelayedCall.debug = True): %s" % (msg,))



class DirtyReactorAggregateError(Exception):
    """
    Passed to L{twisted.trial.itrial.IReporter.addError} when the reactor is
    left in an unclean state after a test.

    @ivar delayedCalls: The L{DelayedCall} objects which weren't cleaned up.
    @ivar selectables: The selectables which weren't cleaned up.
    """

    def __init__(self, delayedCalls, selectables=None):
        self.delayedCalls = delayedCalls
        self.selectables = selectables

    def __str__(self):
        """
        Return a multi-line message describing all of the unclean state.
        """
        msg = "Reactor was unclean."
        if self.delayedCalls:
            msg += ("\nDelayedCalls: (set "
                    "twisted.internet.base.DelayedCall.debug = True to "
                    "debug)\n")
            msg += "\n".join(map(str, self.delayedCalls))
        if self.selectables:
            msg += "\nSelectables:\n"
            msg += "\n".join(map(str, self.selectables))
        return msg



class _Janitor(object):
    """
    The guy that cleans up after you.

    @ivar test: The L{TestCase} to report errors about.
    @ivar result: The L{IReporter} to report errors to.
    @ivar reactor: The reactor to use. If None, the global reactor
        will be used.
    """
    def __init__(self, test, result, reactor=None):
        """
        @param test: See L{_Janitor.test}.
        @param result: See L{_Janitor.result}.
        @param reactor: See L{_Janitor.reactor}.
        """
        self.test = test
        self.result = result
        self.reactor = reactor


    def postCaseCleanup(self):
        """
        Called by L{unittest.TestCase} after a test to catch any logged errors
        or pending L{DelayedCall}s.
        """
        calls = self._cleanPending()
        if calls:
            aggregate = DirtyReactorAggregateError(calls)
            self.result.addError(self.test, Failure(aggregate))
            return False
        return True


    def postClassCleanup(self):
        """
        Called by L{unittest.TestCase} after the last test in a C{TestCase}
        subclass. Ensures the reactor is clean by murdering the threadpool,
        catching any pending L{DelayedCall}s, open sockets etc.
        """
        selectables = self._cleanReactor()
        calls = self._cleanPending()
        if selectables or calls:
            aggregate = DirtyReactorAggregateError(calls, selectables)
            self.result.addError(self.test, Failure(aggregate))
        self._cleanThreads()


    def _getReactor(self):
        """
        Get either the passed-in reactor or the global reactor.
        """
        if self.reactor is not None:
            reactor = self.reactor
        else:
            from twisted.internet import reactor
        return reactor


    def _cleanPending(self):
        """
        Cancel all pending calls and return their string representations.
        """
        reactor = self._getReactor()

        # flush short-range timers
        reactor.iterate(0)
        reactor.iterate(0)

        delayedCallStrings = []
        for p in reactor.getDelayedCalls():
            if p.active():
                delayedString = str(p)
                p.cancel()
            else:
                print "WEIRDNESS! pending timed call not active!"
            delayedCallStrings.append(delayedString)
        return delayedCallStrings
    _cleanPending = utils.suppressWarnings(
        _cleanPending, (('ignore',), {'category': DeprecationWarning,
                                      'message':
                                      r'reactor\.iterate cannot be used.*'}))

    def _cleanThreads(self):
        reactor = self._getReactor()
        if interfaces.IReactorThreads.providedBy(reactor):
            reactor.suggestThreadPoolSize(0)
            if getattr(reactor, 'threadpool', None) is not None:
                try:
                    reactor.removeSystemEventTrigger(
                        reactor.threadpoolShutdownID)
                except KeyError:
                    pass
                # Remove the threadpool, and let the reactor put it back again
                # later like a good boy
                reactor._stopThreadPool()

    def _cleanReactor(self):
        """
        Remove all selectables from the reactor, kill any of them that were
        processes, and return their string representation.
        """
        reactor = self._getReactor()
        selectableStrings = []
        for sel in reactor.removeAll():
            if interfaces.IProcessTransport.providedBy(sel):
                sel.signalProcess('KILL')
            selectableStrings.append(repr(sel))
        return selectableStrings


def suppress(action='ignore', **kwarg):
    """
    Sets up the .suppress tuple properly, pass options to this method as you
    would the stdlib warnings.filterwarnings()

    So, to use this with a .suppress magic attribute you would do the
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

    Note that as with the todo and timeout attributes: the module level
    attribute acts as a default for the class attribute which acts as a default
    for the method attribute. The suppress attribute can be overridden at any
    level by specifying C{.suppress = []}
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



def _runSequentially(callables, stopOnFirstError=False):
    """
    Run the given callables one after the other. If a callable returns a
    Deferred, wait until it has finished before running the next callable.

    @param callables: An iterable of callables that take no parameters.

    @param stopOnFirstError: If True, then stop running callables as soon as
        one raises an exception or fires an errback. False by default.

    @return: A L{Deferred} that fires a list of C{(flag, value)} tuples. Each
        tuple will be either C{(SUCCESS, <return value>)} or C{(FAILURE,
        <Failure>)}.
    """
    results = []
    for f in callables:
        d = defer.maybeDeferred(f)
        thing = defer.waitForDeferred(d)
        yield thing
        try:
            results.append((defer.SUCCESS, thing.getResult()))
        except:
            results.append((defer.FAILURE, Failure()))
            if stopOnFirstError:
                break
    yield results
_runSequentially = defer.deferredGenerator(_runSequentially)



__all__ = ['FailureError', 'DirtyReactorWarning', 'DirtyReactorError',
           'PendingTimedCallsError', 'runSequentially']
