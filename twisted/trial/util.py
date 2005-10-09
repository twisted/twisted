# -*- test-case-name: twisted.trial.test.test_trial -*-
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
from twisted.python import failure, util, log
from twisted.internet import defer, interfaces
from twisted.trial import itrial
import zope.interface as zi

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']

# ---------------------------------

DEFAULT_TIMEOUT = object()
DEFAULT_TIMEOUT_DURATION = 120.0


class SignalStateManager:
    """
    keeps state of signal handlers and provides methods for restoration
    """

    exclude = ['SIGKILL', 'SIGSTOP', 'SIGRTMIN', 'SIGRTMAX']

    def __init__(self):
        self._store = {}

    def save(self):
        for signum in [getattr(signal, n) for n in dir(signal)
                       if n.startswith('SIG') and n[3] != '_'
                       and n not in self.exclude]:
            self._store[signum] = signal.getsignal(signum)

    def restore(self):
        for signum, handler in self._store.iteritems():
            if handler is not None:
                signal.signal(signum, handler)

    def clear(self):
        self._store = {}
            

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


class MultiError(Exception):
    """smuggle a sequence of failures through a raise
    @ivar failures: a sequence of failure objects that prompted the raise
    @ivar args: additional arguments
    """
    def __init__(self, failures, *args):
        if isinstance(failures, failure.Failure):
            self.failures = [failures]
        else:
            self.failures = list(failures)
        self.args = args

    def __str__(self):
        return '\n\n'.join([e.getTraceback() for e in self.failures])


class LoggedErrors(MultiError):
    """raised when there have been errors logged using log.err"""
    
class WaitError(MultiError):
    """raised when there have been errors during a call to wait"""

class JanitorError(MultiError):
    """raised when an error is encountered during a *Cleanup"""

class DirtyReactorError(Exception):
    """emitted when the reactor has been left in an unclean state"""

class DirtyReactorWarning(Warning):
    """emitted when the reactor has been left in an unclean state"""

class PendingTimedCallsError(Exception):
    """raised when timed calls are left in the reactor"""

DIRTY_REACTOR_MSG = "THIS WILL BECOME AN ERROR SOON! reactor left in unclean state, the following Selectables were left over: "
PENDING_TIMED_CALLS_MSG = "pendingTimedCalls still pending (consider setting twisted.internet.base.DelayedCall.debug = True):"


class _Janitor(object):
    logErrCheck = postCase = True
    cleanPending = cleanThreads = cleanReactor = postMethod = True

    def postMethodCleanup(self):
        if self.postMethod:
            return self._dispatch('logErrCheck', 'cleanPending')

    def postCaseCleanup(self):
        if self.postCase:
            return self._dispatch('logErrCheck', 'cleanReactor',
                                  'cleanPending', 'cleanThreads')

    def _dispatch(self, *attrs):
        errors = []
        for attr in attrs:
            if getattr(self, attr):
                try:
                    getattr(self, "do_%s" % attr)()
                except LoggedErrors, e:
                    errors.extend(e.failures)
                except PendingTimedCallsError:
                    errors.append(failure.Failure())
        if errors:
            raise JanitorError([e for e in errors if e is not None])

    def do_logErrCheck(cls):
        if log._keptErrors:
            L = []
            for err in log._keptErrors:
                if isinstance(err, failure.Failure):
                    L.append(err)
                else:
                    L.append(repr(err))
            log.flushErrors()
            raise LoggedErrors(L)
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

            spinWhile(reactor.getDelayedCalls)

            raise PendingTimedCallsError(s)
    do_cleanPending = classmethod(do_cleanPending)

    def do_cleanThreads(cls):
        from twisted.internet import reactor
        if interfaces.IReactorThreads.providedBy(reactor):
            reactor.suggestThreadPoolSize(0)
            if hasattr(reactor, 'threadpool') and reactor.threadpool:
                reactor.threadpool.stop()
                reactor.threadpool = None
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
            # raise DirtyReactorError, s
            raise JanitorError(failure.Failure(DirtyReactorWarning(' '.join(s))))
    do_cleanReactor = classmethod(do_cleanReactor)

    def doGcCollect(cls):
         gc.collect()


def spinUntil(f, timeout=DEFAULT_TIMEOUT_DURATION,
              msg="condition not met before timeout"):
    """spin the reactor while condition returned by f() == False or timeout
    seconds have elapsed i.e. spin until f() is True
    """
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

def _wait(d, timeout=None, running=[]):
    from twisted.internet import reactor

    if running:
        raise WaitIsNotReentrantError, REENTRANT_WAIT_ERROR_MSG
    running.append(None)
    try:
        assert isinstance(d, defer.Deferred), "first argument must be a deferred!"

        results = []
        def append(any):
             if results is not None:
                results.append(any)
        d.addBoth(append)

        if results:
            return results[0]

        def crash(ign):
            if results is not None:
                reactor.crash()

        d.addBoth(crash)

        if timeout is None:
            timeoutCall = None
        else:
            timeoutCall = reactor.callLater(timeout, reactor.crash)

        def stop():
            reactor.crash()

        reactor.stop = stop
        try:
            reactor.run()
        finally:
            del reactor.stop

        if timeoutCall is not None:
            if timeoutCall.active():
                timeoutCall.cancel()
            else:
                raise defer.TimeoutError()

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
    """Waits (spins the reactor) for a Deferred to arrive, then returns or
    throws an exception, based on the result. The difference between this and
    deferredResult is that it actually throws the original exception, not the
    Failure, so synchronous exception handling is much more sane.  

    There are some caveats to follow when using this method:
    
      - There is an important restriction on the use of this method which may
        be difficult to predict at the time you're writing the test.The issue
        is that the reactor's L{twisted.internet.base.runUntilCurrent} is not
        reentrant, therefore wait is B{I{not reentrant!}} This means that you
        cannot call wait from within a callback of a deferred you are waiting
        on. Also, you may or may not be able to call wait on deferreds which
        you have not created, as the originating API may violate this rule
        without your knowledge. For an illustrative example, see 
        L{twisted.trial.test.test_trial.WaitReentrancyTest} 

      - If you are relying on the original traceback for some reason, do
        useWaitError=True. Due to the way that Deferreds and Failures work, the
        presence of the original traceback stack cannot be guaranteed without
        passing this flag (see below).  

    @param timeout: None indicates that we will wait indefinately, the default
        is to wait 4.0 seconds.  
    @type timeout: types.FloatType 

    @param useWaitError: The exception thrown is a
        L{twisted.trial.util.WaitError}, which saves the original failure object
        or objects in a list .failures, to aid in the retrieval of the original
        stack traces.  The tradeoff is between wait() raising the original
        exception *type* or being able to retrieve the original traceback
        reliably. (see issue 769) 
    @type useWaitError: boolean
    """
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
    
    if not useWaitError:
        if isinstance(r, failure.Failure):
            r.raiseException()
    else:
        flist = []
        if isinstance(r, failure.Failure):
            flist.append(r)
        
        if flist:
            raise WaitError(flist)

    return r

def extract_tb(tb, limit=None):
    """Extract a list of frames from a traceback, without unittest internals.

    Functionally identical to L{traceback.extract_tb}, but cropped to just
    the test case itself, excluding frames that are part of the Trial
    testing framework.
    """
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
    """A formatted traceback and exception, without exposing the framework.

    I am identical in function to L{traceback.format_exception},
    but I screen out frames from the traceback that are part of
    the testing framework itself, leaving only the code being tested.
    """
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
    """this method is not supported for the moment and is 
    awaiting a fix (see U{issue627 
    <http://www.twistedmatrix.com/users/roundup.twistd/twisted/issue627>})
    """
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


class UserMethodError(Exception):
    """indicates that the user method had an error, but raised after
    call is complete
    """

class UserMethodWrapper(object):
    def __init__(self, original, raiseOnErr=True, timeout=None, suppress=None):
        self.original = original
        self.timeout = timeout
        self.raiseOnErr = raiseOnErr
        self.errors = []
        self.suppress = suppress
        self.name = original.__name__

    def __call__(self, *a, **kw):
        timeout = getattr(self, 'timeout', None)
        if timeout is None:
            timeout = getattr(self.original, 'timeout', DEFAULT_TIMEOUT)
        self.startTime = time.time()
        def run():
            return wait(defer.maybeDeferred(self.original, *a, **kw),
                        timeout, useWaitError=True)
        try:
            self._runWithWarningFilters(run)
        except MultiError, e:
            for f in e.failures:
                self.errors.append(f)
        except KeyboardInterrupt:
            f = failure.Failure()
            self.errors.append(f)
        self.endTime = time.time()
        for e in self.errors:
            self.errorHook(e)
        if self.raiseOnErr and self.errors:
            raise UserMethodError

    def _runWithWarningFilters(self, f, *a, **kw):
        """calls warnings.filterwarnings(*item[0], **item[1]) 
        for each item in alist, then runs func f(*a, **kw) and 
        resets warnings.filters to original state at end
        """
        filters = warnings.filters[:]
        try:
            if self.suppress is not None:
                for args, kwargs in self.suppress:
                    warnings.filterwarnings(*args, **kwargs)
            return f(*a, **kw)
        finally:
            warnings.filters = filters[:]

    def errorHook(self, fail):
        pass


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


__all__ = ["MultiError", "LoggedErrors", 'WaitError', 'JanitorError', 'DirtyReactorWarning',
           'DirtyReactorError', 'PendingTimedCallsError', 'WaitIsNotReentrantError',
           'deferredResult', 'deferredError', 'wait', 'extract_tb', 'format_exception',
           'suppressWarnings']
