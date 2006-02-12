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

import traceback, warnings, time, signal, gc, sys
from twisted.python import failure, util, log, threadpool
from twisted.internet import utils, defer, interfaces

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']

# ---------------------------------

DEFAULT_TIMEOUT = object()
DEFAULT_TIMEOUT_DURATION = 120.0


def deferredResult(d, timeout=None):
    """
    Waits for a Deferred to arrive, then returns or throws an exception,
    based on the result.
    """
    warnings.warn("Do NOT use deferredResult.  Return a Deferred from your "
                  "test.", stacklevel=2, category=DeprecationWarning)
    result = _wait(d, timeout)
    if isinstance(result, failure.Failure):
        raise result
    else:
        return result

def deferredError(d, timeout=None):
    """
    Waits for deferred to fail, and it returns the Failure.

    If the deferred succeeds, raises FailTest.
    """
    warnings.warn("Do NOT use deferredError.  Return a Deferred from your "
                  "test.", stacklevel=2, category=DeprecationWarning)
    from twisted.trial import unittest
    result = _wait(d, timeout)
    if isinstance(result, failure.Failure):
        return result
    else:
        raise unittest.FailTest, "Deferred did not fail: %r" % (result,)


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
        return self._dispatch('logErrCheck', 'cleanPending')

    def postClassCleanup(self):
        return self._dispatch('logErrCheck', 'cleanReactor',
                              'cleanPending', 'cleanThreads')

    def _dispatch(self, *attrs):
        for attr in attrs:
            getattr(self, "do_%s" % attr)()

    def do_logErrCheck(cls):
        try:
            if len(log._keptErrors) > 0:
                raise FailureError(log._keptErrors[0])
        finally:
            log.flushErrors()
    do_logErrCheck = classmethod(do_logErrCheck)

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

def fireWhenDoneFunc(d, f):
    """Returns closure that when called calls f and then callbacks d.
    """
    def newf(*args, **kw):
        rtn = f(*args, **kw)
        d.callback('')
        return rtn
    return util.mergeFunctionMetadata(f, newf)

def spinUntil(f, timeout=DEFAULT_TIMEOUT_DURATION,
              msg="condition not met before timeout"):
    """spin the reactor while condition returned by f() == False or timeout
    seconds have elapsed i.e. spin until f() is True
    """
    warnings.warn("Do NOT use spinUntil.  Return a Deferred from your "
                  "test.", stacklevel=2, category=DeprecationWarning)
    assert callable(f)
    from twisted.internet import reactor
    now = time.time()
    stop = now + timeout
    while not f():
        if time.time() >= stop:
            raise defer.TimeoutError, msg
        reactor.iterate(0.1)

def spinWhile(f, timeout=DEFAULT_TIMEOUT_DURATION,
              msg="f did not return false before timeout"):
    """spin the reactor while condition returned by f() == True or until
    timeout seconds have elapsed i.e. spin until f() is False
    """
    warnings.warn("Do NOT use spinWhile.  Return a Deferred from your "
                  "test.", stacklevel=2, category=DeprecationWarning)
    assert callable(f)
    from twisted.internet import reactor
    now = time.time()
    stop = now + timeout
    while f():
        if time.time() >= stop:
            raise defer.TimeoutError, msg
        reactor.iterate(0.1)

REENTRANT_WAIT_ERROR_MSG = ("already waiting on a deferred, do not call wait() "
                            "in callbacks or from threads "
                            "until such time as runUntilCurrent becomes "
                            "reentrant. (see issue 781)")

class WaitIsNotReentrantError(Exception):
    pass

_wait_is_running = []
def _wait(d, timeout=None, running=_wait_is_running):
    from twisted.internet import reactor
    if running:
        raise WaitIsNotReentrantError, REENTRANT_WAIT_ERROR_MSG

    results = []
    def append(any):
        if results is not None:
            results.append(any)
    def crash(ign):
        if results is not None:
            reactor.crash()
    def stop():
        reactor.crash()

    running.append(None)
    try:
        d.addBoth(append)
        if results:
            return results[0]
        d.addBoth(crash)
        if timeout is None:
            timeoutCall = None
        else:
            timeoutCall = reactor.callLater(timeout, reactor.crash)
        reactor.stop = stop
        try:
            reactor.run()
        finally:
            del reactor.stop
        if timeoutCall is not None:
            if timeoutCall.active():
                timeoutCall.cancel()
            else:
                f = failure.Failure(defer.TimeoutError('_wait timed out'))
                return f

        if results:
            return results[0]

        # If the timeout didn't happen, and we didn't get a result or
        # a failure, then the user probably aborted the test, so let's
        # just raise KeyboardInterrupt.

        # FIXME: imagine this:
        # web/test/test_webclient.py:
        # exc = self.assertRaises(error.Error, unittest.wait, method(url))
        #
        # wait() will raise KeyboardInterrupt, and assertRaises will
        # swallow it. Therefore, wait() raising KeyboardInterrupt is
        # insufficient to stop trial. A suggested solution is to have
        # this code set a "stop trial" flag, or otherwise notify trial
        # that it should really try to stop as soon as possible.
        raise KeyboardInterrupt()
    finally:
        results = None
        running.pop()


def wait(d, timeout=DEFAULT_TIMEOUT, useWaitError=False):
    """Do NOT use this ever. 
    """
    warnings.warn("Do NOT use wait. It is a bad and buggy and deprecated since "
                  "Twisted 2.2.",
                  category=DeprecationWarning, stacklevel=2)
    if timeout is DEFAULT_TIMEOUT:
        timeout = DEFAULT_TIMEOUT_DURATION
    try:
        r = _wait(d, timeout)
    except KeyboardInterrupt:
        raise
    except:
        #  it would be nice if i didn't have to armor this call like
        # this (with a blank except:, but we *are* calling user code
        r = failure.Failure()

    if isinstance(r, failure.Failure):
        if useWaitError:
            raise FailureError(r)
        else:
            r.raiseException()
    return r

def extract_tb(tb, limit=None):
    """DEPRECATED in Twisted 2.2"""
    warnings.warn("Deprecated in Twisted 2.2", category=DeprecationWarning)
    from twisted.trial import unittest, runner
    l = traceback.extract_tb(tb, limit)
    util_file = __file__.replace('.pyc','.py')
    unittest_file = unittest.__file__.replace('.pyc','.py')
    runner_file = runner.__file__.replace('.pyc','.py')
    framework = [(unittest_file, '_runPhase'), # Tester._runPhase
                 (unittest_file, '_main'),     # Tester._main
                 (runner_file, 'runTest'),     # [ITestRunner].runTest
                 ]
    # filename, line, funcname, sourcetext
    while (l[0][0], l[0][2]) in framework:
        del l[0]

    if (l[-1][0] == unittest_file) and (l[-1][2] in _failureConditionals):
        del l[-1]
    return l

def format_exception(eType, eValue, tb, limit=None):
    """DEPRECATED in Twisted 2.2"""
    warnings.warn("Deprecated in Twisted 2.2", category=DeprecationWarning)
    from twisted.trial import unittest
    result = [x.strip()+'\n' for x in
              failure.Failure(eValue,eType,tb).getBriefTraceback().split('\n')]
    return result
    # Only mess with tracebacks if they are from an explicitly failed
    # test.
    # XXX isinstance
    if eType != unittest.FailTest:
        return traceback.format_exception(eType, eValue, tb, limit)

    tb_list = extract_tb(tb, limit)

    l = ["Traceback (most recent call last):\n"]
    l.extend(traceback.format_list(tb_list))
    l.extend(traceback.format_exception_only(eType, eValue))
    return l

def suppressWarnings(f, *warningz):
    warnings.warn("Don't use this.  Use the .suppress attribute instead",
                  category=DeprecationWarning, stacklevel=2)
    def enclosingScope(warnings, warningz):
        exec """def %s(*args, **kwargs):
    for warning in warningz:
        warnings.filterwarnings('ignore', *warning)
    try:
        return f(*args, **kwargs)
    finally:
        for warning in warningz:
            warnings.filterwarnings('default', *warning)
""" % (f.func_name,) in locals()
        return locals()[f.func_name]
    return enclosingScope(warnings, warningz)


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


def timedRun(timeout, f, *a, **kw):
    return wait(defer.maybeDeferred(f, *a, **kw), timeout, useWaitError=True)


def testFunction(f):
    containers = [f] + getPythonContainers(f)
    suppress = acquireAttribute(containers, 'suppress', [])
    timeout = acquireAttribute(containers, 'timeout', DEFAULT_TIMEOUT)
    return utils.runWithWarningsSuppressed(suppress, timedRun, timeout, f)


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
           'PendingTimedCallsError', 'WaitIsNotReentrantError',
           'deferredResult', 'deferredError', 'wait', 'extract_tb',
           'format_exception', 'suppressWarnings']
