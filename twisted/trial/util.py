# -*- test-case-name: twisted.test.test_trial -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#

import traceback
from twisted.python import components, failure
from twisted.internet import interfaces

# Methods in this list will be omitted from a failed test's traceback if
# they are the final frame.
_failureConditionals = [
    'fail', 'failIf', 'failUnless', 'failUnlessRaises', 'failUnlessEqual',
    'failUnlessIdentical', 'failIfEqual', 'assertApproximates']


def reactorCleanUp():
    from twisted.internet import reactor
    reactor.iterate() # flush short-range timers
    pending = reactor.getDelayedCalls()
    if pending:
        msg = "\npendingTimedCalls still pending:\n"
        for p in pending:
            msg += " %s\n" % p
        from warnings import warn
        warn(msg)
        for p in pending: p.cancel() # delete the rest
        reactor.iterate() # flush them
        raise unittest.FailTest, msg
    if components.implements(reactor, interfaces.IReactorThreads):
        reactor.suggestThreadPoolSize(0)
        if hasattr(reactor, 'threadpool') and reactor.threadpool:
            reactor.threadpool.stop()
            reactor.threadpool = None

def isTestClass(testClass):
    return issubclass(testClass, unittest.TestCase)

def isTestCase(testCase):
    return isinstance(testCase, unittest.TestCase)

def _getDeferredResult(d, timeout=None):
    from twisted.internet import reactor
    if timeout is not None:
        d.setTimeout(timeout)
    resultSet = []
    d.addCallbacks(resultSet.append, resultSet.append)
    while not resultSet:
        reactor.iterate()
    return resultSet[0]

def deferredResult(d, timeout=None):
    """Waits for a Deferred to arrive, then returns or throws an exception,
    based on the result.
    """
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        raise result
    else:
        return result

def deferredError(d, timeout=None):
    """Waits for deferred to fail, and it returns the Failure.

    If the deferred succeeds, raises FailTest.
    """
    result = _getDeferredResult(d, timeout)
    if isinstance(result, failure.Failure):
        return result
    else:
        raise unittest.FailTest, "Deferred did not fail: %r" % result


def extract_tb(tb, limit=None):
    """Extract a list of frames from a traceback, hiding unittest internals.

    Functionally identical to L{traceback.extract_tb}, but cropped to just
    the test case itself, excluding frames that are part of the Trial
    testing framework.
    """
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

def emacs_format_exception(eType, eValue, tb, limit=None):
    """Compact traceback formatting, parseable by emacs compile-mode.
    """

    # TODO: hide trial frames like plain_format_exception
    l = traceback.extract_tb(tb, limit)
    return ['%s:%s:%s\n' % x[:-1] for x in l]

def plain_format_exception(eType, eValue, tb, limit=None):
    """Emit a formatted traceback and exception, but hide trial's framework.

    I am identical in function to L{traceback.format_exception},
    but I screen out frames from the traceback that are part of
    the testing framework itself, leaving only the code being tested.
    """
    tb_list = extract_tb(tb, limit)

    l = ["Traceback (most recent call last):\n"]
    l.extend(traceback.format_list(tb_list))
    l.extend(traceback.format_exception_only(eType, eValue))
    return l

# sibling imports, ugh.
import unittest
import runner
