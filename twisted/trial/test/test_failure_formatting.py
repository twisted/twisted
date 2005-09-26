# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import re, os, sys

from twisted.trial.test import erroneous, common
from twisted.trial import itrial, unittest, reporter, runner
from twisted.python import failure

from pprint import pformat, pprint

class BogusError(Exception):
    pass

ERROR_MSG = "i did something dumb"


def trimFilename(name, N):
    """extracts the last N path elements of a path and returns them
    as a string, preceeded by an elipsis and separated by os.sep
    """
    # XXX: this function is *not* perfect
    # if N > num path elements you still get an elipsis prepended
    L = []
    drive, name = os.path.splitdrive(name)
    while 1:
        head, tail = os.path.split(name)
        L.insert(0, tail)
        if not head or head == os.sep:
            break
        name = head
    if drive:
        L.insert(0, drive)
    if len(L) <= N:
        ret = "%s" % (os.path.join(*L),)
    else:
        ret = "...%s" % os.path.join(*L[-N:])
    return ret


def gimmeAFailure():
    f = None
    try:
        raise BogusError, ERROR_MSG
    except:
        f = failure.Failure()
    return f

re_psep = re.escape(os.sep)

expectFailureInSetUp = [re.compile(r'.*twisted%(sep)sinternet%(sep)sdefer.py.*maybeDeferred' % {'sep': re_psep}), # XXX: this may break
                        None,
                        re.compile(r'.*test%(sep)serroneous.py.*in setUp' % {'sep': re_psep}),
                        re.compile(r'.*raise FoolishError.*'),
                        re.compile(r'.*erroneous.FoolishError: I am a broken setUp method')]

expectTestFailure = ['Running 1 tests.',
                     re.compile('.*'),
                     re.compile('.*'),
                     reporter.DOUBLE_SEPARATOR,
                     '[FAIL]: twisted.trial.test.common.FailfulTests.testFailure',
                     None,
                     None,
                     re.compile(r'.*common.py.*in testFailure'),
                     None,
                     'twisted.trial.unittest.FailTest: %s' % (common.FAILURE_MSG,)]

class TestFailureFormatting(common.RegistryBaseMixin, unittest.TestCase):
    def setUp(self):
        super(TestFailureFormatting, self).setUp()
        self.loader = runner.TestLoader()
    
    def testFormatErroredMethod(self):
        self.suite.run(self.loader.loadClass(erroneous.TestFailureInSetUp))
        
        expect = ['Running 1 tests.',
                  re.compile('.*'),
                  re.compile('.*'),
                  reporter.DOUBLE_SEPARATOR,
                  '[ERROR]: twisted.trial.test.erroneous.TestFailureInSetUp.testMethod']

        expect.extend(expectFailureInSetUp)

        self.stringComparison(expect, self.suite.reporter.out.splitlines())

    def testFormatFailedMethod(self):
        self.suite.run(self.loader.loadMethod(
            common.FailfulTests.testFailure))

        self.stringComparison(expectTestFailure,
                                self.suite.reporter.out.splitlines())

    def testTrimFilename(self):
        self.checkReporterSetup = False
        path = os.sep.join(['foo', 'bar', 'baz', 'spam', 'spunk'])

        out = trimFilename(path, 3)
        s = "...%s" % (os.sep.join(['baz','spam','spunk']),)
        self.assertEqual(out, s)
        
        out = trimFilename(path, 10)
        s = os.sep.join(['foo','bar','baz','spam','spunk'])
        self.assertEqual(out, s)

    def testDoctestError(self):
        if sys.version_info[0:2] < (2, 3):
            raise unittest.SkipTest(
                'doctest support only works in Python 2.3 or later')
        from twisted.trial.test import trialdoctest2
        self.suite.run(self.loader.loadDoctests(trialdoctest2))
        output = self.suite.reporter.out.splitlines()
        path = 'twisted.trial.test.trialdoctest2.unexpectedException'
        expect = ['Running 1 tests.',
                  re.compile('.*'),
                  reporter.DOUBLE_SEPARATOR,
                  re.compile(r'\[(ERROR|FAIL)\]: .*[Dd]octest.*'
                             + re.escape(path))]
        self.stringComparison(expect, output)
        output = '\n'.join(output)
        for substring in ['1/0', 'ZeroDivisionError',
                          'Exception raised:',
                          'twisted.trial.test.trialdoctest2.unexpectedException']:
            self.assertSubstring(substring, output)
        self.failUnless(
            re.search('Fail(ed|ure in) example:', output),
            "Couldn't match 'Failure in example: ' or 'Failed example: '")
