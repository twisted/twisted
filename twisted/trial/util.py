# -*- test-case-name: twisted.test.test_trial -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan Simms <slyphon@twistedmatrix.com>
#         and countless contributors
#
from __future__ import generators

import traceback, warnings, new, inspect, types, time, signal
from twisted.python import components, failure, util, log, reflect
from twisted.internet import defer, reactor, interfaces
from twisted.trial import itrial
import zope.interface as zi

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']


# -- helpful internal adapters --

def _getModuleNameFromModuleType(obj):
    return obj.__name__

def _getModuleNameFromClassType(obj):
    # also for types.InstanceType
    return obj.__module__

def _getModuleNameFromMethodType(obj):
    return obj.im_class.__module__

def _getModuleNameFromFunctionType(obj):
    return obj.func_globals['__name__']
        
def _getClassNameFromClass(obj):
    return obj.__name__

def _getClassNameFromMethodType(obj):
    return obj.im_class.__name__

def _getFQClassName(obj):
    return "%s.%s" % (itrial.IModuleName(obj), itrial.IClassName(obj))

def _getFQMethodName(obj):
    return "%s.%s" % (itrial.IFQClassName(obj), obj.__name__)

def _getClassFromMethodType(obj):
    return obj.im_class

def _getModuleFromMethodType(obj):
    return reflect.namedModule(obj.im_class.__module__)

def _getClassFromFQString(obj):
    return reflect.namedAny(obj)

# ---------------------------------

class SignalStateManager:
    """keeps state of signal handlers and provides methods for restoration"""
    def __init__(self):
        self._store = {}

    def save(self):
        for signum in [getattr(signal, n) for n in dir(signal)
                       if n.startswith('SIG') and n[3] != '_']:
            self._store[signum] = signal.getsignal(signum)

    def restore(self):
        for signum, handler in self._store.iteritems():
            if handler is not None:
                signal.signal(signum, handler)

    def clear(self):
        self._store = {}
            

def _append(result, lst):
    lst.append(result)

def _getDeferredResult(d, timeout=None):
    from twisted.internet import reactor
    if timeout is not None:
        d.setTimeout(timeout)
    resultSet = []
    d.addBoth(_append, resultSet)
    while not resultSet:
        reactor.iterate(0.01)
    return resultSet[0]

def deferredResult(d, timeout=None):
    """This function is DEPRECATED
    
    Waits for a Deferred to arrive, then returns or throws an exception,
    based on the result.
    """
    warnings.warn(("twisted.trial.util.deferredResult is DEPRECATED! "
                   "Return a deferred from your test method, "
                   "and trial will do the Right Thing"), DeprecationWarning)
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        raise result
    else:
        return result


class MultiErrorFailure(object):
    def __init__(self, original):
        self.value = [original]

class LoggedErrors(Exception):
    """raised when there have been errors logged using log.err"""

class DirtyReactorError(Exception):
    """emitted when the reactor has been left in an unclean state"""

class DirtyReactorWarning(Warning):
    """emitted when the reactor has been left in an unclean state"""

class PendingTimedCallsError(Exception):
    """raised when timed calls are left in the reactor"""

DIRTY_REACTOR_MSG = "THIS WILL BECOME AN ERROR SOON! reactor left in unclean state, the following Selectables were left over: "
PENDING_TIMED_CALLS_MSG = "pendingTimedCalls still pending (consider setting twisted.internet.base.DelayedCall.debug = True):"


class Janitor(object):
    zi.implements(itrial.IJanitor)
    logErrCheck = postCase = True
    cleanPending = cleanThreads = cleanReactor = postMethod = True

    def postMethodCleanup(self):
        if self.postMethod:
            return self._dispatch('logErrCheck', 'cleanPending')

    def postCaseCleanup(self):
        if self.postCase:
            return self._dispatch('logErrCheck', 'cleanReactor', 'cleanPending', 'cleanThreads')

    def _dispatch(self, *attrs):
        errors = []
        for attr in attrs:
            if getattr(self, attr):
                try:
                    getattr(self, "do_%s" % attr)()
                except:
                    errors.append(failure.Failure())
        return errors

    def do_logErrCheck(cls):
        if log._keptErrors:
            L = []
            for err in log._keptErrors:
                if isinstance(err, failure.Failure):
                    L.append(err.getTraceback())
                else:
                    L.append(repr(err))
            log.flushErrors()
            raise LoggedErrors, '\n\n'.join(L)
    do_logErrCheck = classmethod(do_logErrCheck)

    def do_cleanPending(cls):
        s = None
        reactor.iterate(0.01) # flush short-range timers
        pending = reactor.getDelayedCalls()
        if pending:
            s = PENDING_TIMED_CALLS_MSG

            for p in pending:
                s += " %s\n" % (p,)

            for p in pending:
                p.cancel() # delete the rest

            reactor.iterate(0.01) # flush them

        if s is not None:
            raise PendingTimedCallsError, s
    do_cleanPending = classmethod(do_cleanPending)

    def do_cleanThreads(cls):
        if interfaces.IReactorThreads.providedBy(reactor):
            reactor.suggestThreadPoolSize(0)
            if hasattr(reactor, 'threadpool') and reactor.threadpool:
                reactor.threadpool.stop()
                reactor.threadpool = None
    do_cleanThreads = classmethod(do_cleanThreads)

    def do_cleanReactor(cls):
        s = None
        if interfaces.IReactorCleanup.providedBy(reactor):
            junk = reactor.cleanup()
            if junk:
                s = DIRTY_REACTOR_MSG + repr([repr(obj) for obj in junk])
        if s is not None:
            # raise DirtyReactorError, s
            warnings.warn(s, DirtyReactorWarning)

    do_cleanReactor = classmethod(do_cleanReactor)

    def doGcCollect(cls):
         if gc:
             gc.collect()



def _wait(d, timeout=None):
#    this is private and should only be used by trial!
#    if you use this function directly YOU WILL UNLEASH THE
#    WHITESPACE-EATING NANOVIRUSES!

#    B{YOU HAVE BEEN WARNED!}
    from twisted.trial import unittest, itrial 
    from twisted.internet import reactor

    def _dbg(msg):
        log.msg(iface=itrial.ITrialDebug, timeout=msg)

    end = start = time.time()

    itimeout = itrial.ITimeout(timeout)

    end += float(itimeout.duration)

    resultSet = []
    d.addBoth(resultSet.append)
    while not resultSet:
        if itimeout.duration >= 0.0 and time.time() > end:
            raise itimeout.excClass, itimeout.excArg
        reactor.iterate(0.01)
    r = resultSet[0]
    if isinstance(r, failure.Failure):
        r.raiseException()
    Janitor.do_logErrCheck()
    return r


def wait(d, timeout=None):
    """Waits (spins the reactor) for a Deferred to arrive, then returns
    or throws an exception, based on the result. The difference
    between this and deferredResult is that it actually throws the
    original exception, not the Failure, so synchronous exception
    handling is much more sane.
    @param timeout: None indicates the default timeout period of 4.0 seconds,
    pass a number to set it to some other value
    @type timeout: types.FloatType
    """
##     warnings.warn(("twisted.trial.util.wait is DEPRECATED! "
##                    "Return a deferred from your test method,"
##                    " and trial will do the Right Thing"), DeprecationWarning, stacklevel=2)
    return _wait(d, timeout)


def deferredError(d, timeout=None):
    """This function is DEPRECATED
    Waits for deferred to fail, and it returns the Failure.

    If the deferred succeeds, raises FailTest.
    """
    warnings.warn(("twisted.trial.util.deferredError is DEPRECATED! "
                   "Return a deferred from your test "
                   "method, and trial will do the Right Thing"), DeprecationWarning, stacklevel=2)
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        return result
    else:
        from twisted.trial import unittest
        raise unittest.FailTest, "Deferred did not fail: %r" % (result,)


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


def classesToTestWithTrial(*cls):
    from twisted.trial import itrial 
    for c in cls:
        zi.directlyProvides(c, itrial.IPyUnitTCFactory)
        #zi.directlyProvides(c, itrial.ITestCaseFactory)


class StdioProxy(util.SubclassableCStringIO):
    def __init__(self, original):
        super(StdioProxy, self).__init__()
        self.original = original

    def __iter__(self):
        return self.original.__iter__()

    def write(self, s):
        super(StdioProxy, self).write(s)
        return self.original.write(s)

    def writelines(self, list):
        super(StdioProxy, self).writelines(list)
        return self.original.writelines(list)

    def flush(self):
        return self.original.flush()

    def next(self):
        return self.original.next()

    def close(self):
        return self.original.close()

    def isatty(self):
        return self.original.isatty()

    def seek(self, pos, mode=0):
        return self.original.seek(pos, mode)

    def tell(self):
        return self.original.tell()

    def read(self, n=-1):
        return self.original.read(n)

    def readline(self, length=None):
        return self.original.readline(length)

    def readlines(self, sizehint=0):
        return self.original.readlines(sizehint)

    def truncate(self, size=None):
        return self.original.truncate(size)

        
class TrialLogObserver(object):
    def __init__(self):
        self.events = []

    def __call__(self, eventDict):
        d = eventDict.copy()
        # don't include our internal log events as part of the
        # test run's log events
        #
        from twisted.trial.itrial import ITrialDebug
        iface = d.get('iface', None)
        if iface is not None and iface is ITrialDebug:
            return
        self.events.append(d)
        
    def install(self):
        log.addObserver(self)
        return self

    def remove(self):
        if self in log.theLogPublisher.observers:
            log.removeObserver(self)


# -- backwards compatibility code for 2.2 ---

try:
    from itertools import chain as iterchain
except ImportError:
    def iterchain(*iterables):
        for it in iterables:
            for element in it:
                yield element

