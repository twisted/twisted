# -*- test-case-name: twisted.trial.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
A collection of utility functions and classes, used internally by Trial.

This code is for Trial's internal use.  Do NOT use this code if you are writing
tests.  It is subject to change at the Trial maintainer's whim.  There is
nothing here in this module for you to use unless you are maintaining Trial.

Any non-Trial Twisted code that uses this module will be shot.

Maintainer: Jonathan Lange

@var DEFAULT_TIMEOUT_DURATION: The default timeout which will be applied to
    asynchronous (ie, Deferred-returning) test methods, in seconds.
"""

from __future__ import division, absolute_import, print_function

import traceback, sys
from random import randrange

from twisted.python.compat import _PY3, reraise
from twisted.internet import defer, _utilspy3 as utils, interfaces
from twisted.python.failure import Failure
from twisted.python import deprecate, versions
from twisted.python.filepath import FilePath

__all__ = [
    'DEFAULT_TIMEOUT_DURATION',

    'excInfoOrFailureToExcInfo', 'suppress', 'acquireAttribute']

DEFAULT_TIMEOUT = object()
DEFAULT_TIMEOUT_DURATION = 120.0



class DirtyReactorAggregateError(Exception):
    """
    Passed to L{twisted.trial.itrial.IReporter.addError} when the reactor is
    left in an unclean state after a test.

    @ivar delayedCalls: The L{DelayedCall<twisted.internet.base.DelayedCall>}
        objects which weren't cleaned up.
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
        or pending L{DelayedCall<twisted.internet.base.DelayedCall>}s.
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
        catching any pending
        L{DelayedCall<twisted.internet.base.DelayedCall>}s, open sockets etc.
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
                print("WEIRDNESS! pending timed call not active!")
            delayedCallStrings.append(delayedString)
        return delayedCallStrings
    _cleanPending = utils.suppressWarnings(
        _cleanPending, (('ignore',), {'category': DeprecationWarning,
                                      'message':
                                      r'reactor\.iterate cannot be used.*'}))

    def _cleanThreads(self):
        reactor = self._getReactor()
        if interfaces.IReactorThreads.providedBy(reactor):
            if reactor.threadpool is not None:
                # Stop the threadpool now so that a new one is created. 
                # This improves test isolation somewhat (although this is a
                # post class cleanup hook, so it's only isolating classes
                # from each other, not methods from each other).
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



_DEFAULT = object()
def acquireAttribute(objects, attr, default=_DEFAULT):
    """
    Go through the list 'objects' sequentially until we find one which has
    attribute 'attr', then return the value of that attribute.  If not found,
    return 'default' if set, otherwise, raise AttributeError.
    """
    for obj in objects:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    if default is not _DEFAULT:
        return default
    raise AttributeError('attribute %r not found in %r' % (attr, objects))



def excInfoOrFailureToExcInfo(err):
    """
    Coerce a Failure to an _exc_info, if err is a Failure.

    @param err: Either a tuple such as returned by L{sys.exc_info} or a
        L{Failure} object.
    @return: A tuple like the one returned by L{sys.exc_info}. e.g.
        C{exception_type, exception_object, traceback_object}.
    """
    if isinstance(err, Failure):
        # Unwrap the Failure into a exc_info tuple.
        err = (err.type, err.value, err.getTracebackObject())
    return err



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



# This should be deleted, and replaced with twisted.application's code; see
# #6016:
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

deprecate.deprecatedModuleAttribute(
    versions.Version("Twisted", 12, 3, 0),
    "This function never worked correctly.  Implement lookup on your own.",
    __name__, "getPythonContainers")


deprecate.deprecatedModuleAttribute(
    versions.Version("Twisted", 10, 1, 0),
    "Please use twisted.python.reflect.namedAny instead.",
    __name__, "findObject")



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
                reraise(exc_info[1], exc_info[2])
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



class _NoTrialMarker(Exception):
    """
    No trial marker file could be found.

    Raised when trial attempts to remove a trial temporary working directory
    that does not contain a marker file.
    """



def _removeSafely(path):
    """
    Safely remove a path, recursively.

    If C{path} does not contain a node named C{_trial_marker}, a
    L{_NoTrialMarker} exception is raised and the path is not removed.
    """
    if not path.child(b'_trial_marker').exists():
        raise _NoTrialMarker(
            '%r is not a trial temporary path, refusing to remove it'
            % (path,))
    try:
        path.remove()
    except OSError as e:
        print ("could not remove %r, caught OSError [Errno %s]: %s"
               % (path, e.errno, e.strerror))
        try:
            newPath = FilePath(b'_trial_temp_old' +
                               str(randrange(10000000)).encode("utf-8"))
            path.moveTo(newPath)
        except OSError as e:
            print ("could not rename path, caught OSError [Errno %s]: %s"
                   % (e.errno,e.strerror))
            raise



class _WorkingDirectoryBusy(Exception):
    """
    A working directory was specified to the runner, but another test run is
    currently using that directory.
    """



def _unusedTestDirectory(base):
    """
    Find an unused directory named similarly to C{base}.

    Once a directory is found, it will be locked and a marker dropped into it to
    identify it as a trial temporary directory.

    @param base: A template path for the discovery process.  If this path
        exactly cannot be used, a path which varies only in a suffix of the
        basename will be used instead.
    @type base: L{FilePath}

    @return: A two-tuple.  The first element is a L{FilePath} representing the
        directory which was found and created.  The second element is a locked
        L{FilesystemLock<twisted.python.lockfile.FilesystemLock>}.  Another
        call to C{_unusedTestDirectory} will not be able to reused the the
        same name until the lock is released, either explicitly or by this
        process exiting.
    """
    from twisted.python.lockfile import FilesystemLock
    counter = 0
    while True:
        if counter:
            testdir = base.sibling('%s-%d' % (base.basename(), counter))
        else:
            testdir = base

        testDirLock = FilesystemLock(testdir.path + '.lock')
        if testDirLock.lock():
            # It is not in use
            if testdir.exists():
                # It exists though - delete it
                _removeSafely(testdir)

            # Create it anew and mark it as ours so the next _removeSafely on it
            # succeeds.
            testdir.makedirs()
            testdir.child('_trial_marker').setContent('')
            return testdir, testDirLock
        else:
            # It is in use
            if base.basename() == '_trial_temp':
                counter += 1
            else:
                raise _WorkingDirectoryBusy()

# Remove this, and move lockfile import, after ticket #5960 is resolved:
if _PY3:
    del _unusedTestDirectory
