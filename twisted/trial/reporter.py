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

import sys, time, pdb, string, types, inspect, traceback

from twisted.python import reflect, failure

# test results, passed as resultType to Reporter.reportResults()
SKIP, EXPECTED_FAILURE, FAILURE, ERROR, UNEXPECTED_SUCCESS, SUCCESS = \
      "skip", "expected failure", "failure", "error", "unexpected success", \
      "success"

class Reporter:
    """I report results from a run of a test suite.

    In all lists below, 'Results' are either a twisted.python.failure.Failure
    object, an exc_info tuple, or a string.
    
    @ivar errors: Tests which have encountered an error.
    @type errors: List of (testClass, method, Results) tuples.
    @ivar failures: Tests which have failed.
    @type failures: List of (testClass, method, Results) tuples.
    @ivar skips: Tests which have been skipped.
    @type skips: List of (testClass, method, Results) tuples.
    @ivar expectedFailures: Tests which failed but are marked as 'todo'
    @type expectedFailures: List of (testClass, method, Results) tuples.
    @ivar unexpectedSuccesses: Tests which passed but are marked as 'todo'
    @type unexpectedSuccesses: List of (testClass, method, Results) tuples.
    @ivar imports: Import errors encountered while assembling the test suite.
    @type imports: List of (moduleName, exception) tuples.

    @ivar numTests: The number of tests I have reports for.
    @type numTests: int
    @ivar expectedTests: The number of tests I expect to run.
    @type expectedTests: int
    @ivar debugger: Run the debugger when encountering a failing test.
    @type debugger: bool
    """
    def __init__(self):
        self.errors = []
        self.failures = []
        self.skips = []
        self.expectedFailures = []
        self.unexpectedSuccesses = []
        self.imports = []
        self.numTests = 0
        self.expectedTests = 0
        self.debugger = False

    def start(self, expectedTests):
        self.expectedTests = expectedTests
        self.startTime = time.time()

    def reportImportError(self, name, exc):
        self.imports.append((name, exc))

    def reportStart(self, testClass, method):
        pass

    def reportResults(self, testClass, method, resultType, results=None):
        tup = (testClass, method, results)
        self.numTests += 1
        if resultType in (FAILURE, ERROR, EXPECTED_FAILURE):
            if self.debugger:
                if isinstance(results, failure.Failure):
                    print "Failure, not Exception -- can't postmortem."
                    pdb.set_trace()
                else:
                    pdb.post_mortem(results[2])
        if resultType == SKIP:
            self.skips.append(tup)
        elif resultType == FAILURE:
            self.failures.append(tup)
        elif resultType == EXPECTED_FAILURE:
            self.expectedFailures.append(tup)
        elif resultType == ERROR:
                self.errors.append(tup)
        elif resultType == UNEXPECTED_SUCCESS:
            self.unexpectedSuccesses.append(tup)
        elif resultType == SUCCESS:
            pass # SUCCESS COUNTS FOR NOTHING!
        else:
            raise ValueError, "bad value for resultType: %s" % resultType
        
    def getRunningTime(self):
        if hasattr(self, 'stopTime'):
            return self.stopTime - self.startTime
        else:
            return time.time() - self.startTime

    def allPassed(self):
        return not (self.errors or self.failures)

    def stop(self):
        self.stopTime = time.time()

class MinimalReporter(Reporter):

    def __init__(self, fp):
        Reporter.__init__(self)
        self.fp = fp

    def stop(self):
        Reporter.stop(self)
        t =  (self.getRunningTime(), self.expectedTests, self.numTests,
               len(self.imports), len(self.errors), len(self.failures),
               len(self.skips))
        self.fp.write(' '.join(map(str,t))+'\n')

class TextReporter(Reporter):
    SEPARATOR = '-' * 79
    DOUBLE_SEPARATOR = '=' * 79

    def __init__(self, stream=sys.stdout, tbformat='plain'):
        self.stream = stream
        self.tbformat = tbformat
        Reporter.__init__(self)

    def reportResults(self, testClass, method, resultType, results=None):
        letters = {SKIP: 'S', EXPECTED_FAILURE: 'T',
                   FAILURE: 'F', ERROR: 'E',
                   UNEXPECTED_SUCCESS: '!', SUCCESS: '.'}
        self.write(letters.get(resultType, '?'))
        Reporter.reportResults(self, testClass, method, resultType, results)

    def _formatError(self, flavor, (testClass, method, error)):
        if isinstance(error, failure.Failure):
            tb = error.getBriefTraceback()
        elif isinstance(error, types.TupleType):
            d = {'plain': traceback,
                 'emacs': util}
            tb = ''.join(d[self.tbformat].format_exception(*error))
        else:
            tb = "%s\n" % error

        ret = ("%s\n%s: %s (%s)\n%s\n%s" %
               (self.DOUBLE_SEPARATOR,
                flavor, method.__name__, reflect.qual(testClass),
                self.SEPARATOR,
                tb))
        return ret

    def _formatImportError(self, name, error):
        if isinstance(error, failure.Failure):
            what = error.getBriefTraceback()
        elif type(error) == types.TupleType:
            what = error.args[0]
        else:
            what = "%s\n" % error
        ret = "Could not import %s: %s\n" % (name, what)
        return ret
    
    def write(self, format, *args):
        if args:
            self.stream.write(format % args)
        else:
            self.stream.write(format)
        self.stream.flush()

    def writeln(self, format=None, *args):
        if format is not None:
            self.stream.write(format % args)
        self.stream.write('\n')
        self.stream.flush()

    def _statusReport(self):
        summaries = []
        if self.failures:
            summaries.append('failures=%d' % len(self.failures))
        if self.errors:
            summaries.append('errors=%d' % len(self.errors))
        if self.skips:
            summaries.append('skips=%d' % len(self.skips))
        if self.expectedFailures:
            summaries.append('expectedFailures=%d' % \
                             len(self.expectedFailures))
        if self.unexpectedSuccesses:
            summaries.append('unexpectedSuccesses=%d' % \
                             len(self.unexpectedSuccesses))
        summary = (summaries and ' ('+', '.join(summaries)+')') or ''
        if self.failures or self.errors:
            # maybe include self.unexpectedSuccesses here
            # do *not* include self.expectedFailures.. that's the whole point
            status = 'FAILED'
        else:
            status = 'OK'
        return '%s%s' % (status, summary)

    def stop(self):
        Reporter.stop(self)
        self.writeln()
        for error in self.skips:
            self.write(self._formatError('SKIPPED', error))
        for error in self.expectedFailures:
            self.write(self._formatError('EXPECTED FAILURE', error))
        for error in self.unexpectedSuccesses:
            self.write(self._formatError('UNEXPECTED SUCCESS', error))
        for error in self.failures:
            self.write(self._formatError('FAILURE', error))
        for error in self.errors:
            self.write(self._formatError('ERROR', error))
        self.writeln(self.SEPARATOR)
        self.writeln('Ran %d tests in %.3fs', self.numTests, self.getRunningTime())
        if self.imports:
            self.writeln()
            for name, error in self.imports:
                self.write(self._formatImportError(name, error))
        self.writeln()
        self.writeln(self._statusReport())

class TimingTextReporter(TextReporter):

    def reportStart(self, testClass, method):
        self.testStartedAt = time.time()
        self.write('%s (%s) ... ', method.__name__, reflect.qual(testClass))

    def reportResults(self, testClass, method, resultType, results=None):
        stopped = time.time()
        t = stopped-self.testStartedAt
        words = {SKIP: '[SKIPPED]',
                 EXPECTED_FAILURE: '[TODO]',
                 FAILURE: '[FAIL]', ERROR: '[ERROR]',
                 UNEXPECTED_SUCCESS: '[SUCCESS!?!]',
                 SUCCESS: '[OK]'}
        self.writeln(words.get(resultType, "[??]")+" "+"(%.02f secs)" % t)
        Reporter.reportResults(self, testClass, method, resultType, results)

class VerboseTextReporter(TextReporter):

    def reportStart(self, testClass, method):
        self.write('%s (%s) ... ', method.__name__, reflect.qual(testClass))

    def reportResults(self, testClass, method, resultType, results=None):
        words = {SKIP: '[SKIPPED]',
                 EXPECTED_FAILURE: '[TODO]',
                 FAILURE: '[FAIL]', ERROR: '[ERROR]',
                 UNEXPECTED_SUCCESS: '[SUCCESS!?!]',
                 SUCCESS: '[OK]'}
        self.writeln(words.get(resultType, "[??]"))
        Reporter.reportResults(self, testClass, method, resultType, results)

class TreeReporter(TextReporter):
    columns = 79

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    def __init__(self, stream=sys.stdout, tbformat='plain'):
        TextReporter.__init__(self, stream, tbformat)
        self.lastModule = None
        self.lastClass = None

    def reportStart(self, testClass, method):
        if testClass.__module__ != self.lastModule:
            self.writeln(testClass.__module__)
            self.lastModule = testClass.__module__
        if testClass != self.lastClass:
            self.writeln('  %s' % testClass.__name__)
            self.lastClass = testClass

        docstr = inspect.getdoc(method)
        if docstr:
            # inspect trims whitespace on the left; the lstrip here is
            # for those odd folks who start docstrings with a blank line.
            what = docstr.lstrip().split('\n', 1)[0]
        else:
            what = method.__name__
        self.currentLine = '    %s ... ' % (what,)
        self.write(self.currentLine)

    def color(self, text, color):
        return '%s%s;1m%s%s0m' % ('\x1b[', color, text, '\x1b[')

    def endLine(self, message, color):
        spaces = ' ' * (self.columns - len(self.currentLine) - len(message))
        self.write(spaces)
        self.writeln(self.color(message, color))

    def reportResults(self, testClass, method, resultType, results=None):
        words = {SKIP: ('[SKIPPED]', self.BLUE),
                 EXPECTED_FAILURE: ('[TODO]', self.BLUE),
                 FAILURE: ('[FAIL]', self.RED),
                 ERROR: ('[ERROR]', self.RED),
                 UNEXPECTED_SUCCESS: ('[SUCCESS!?!]', self.RED),
                 SUCCESS: ('[OK]', self.GREEN)}
        text = words.get(resultType, ('[??]', self.BLUE))
        self.endLine(text[0], text[1])
        Reporter.reportResults(self, testClass, method, resultType, results)

import util
