"""
Twisted Test Framework
"""

from twisted.python import reflect
import sys, time, string, traceback, types, os, glob

class TestCase:
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def fail(self, message=None):
        raise AssertionError, msg

    def failIf(self, condition, message=None):
        if condition:
            raise AssertionError, msg

    def failUnless(self, condition, message=None):
        if not condition:
            raise AssertionError, msg

    def failUnlessRaises(self, exception, f, *args, **kwargs):
        try:
            f(*args, **kwargs)
        except exception:
            pass
        else:
            raise AssertionError, exception.__name__

    def failUnlessEqual(self, first, second, msg=None):
        if not first == second:
            raise AssertionError, (msg or '%s != %s' (first, second))

    def failIfEqual(self, first, second, msg=None):
        if first == second:
            raise AssertionError, (msg or '%s == %s' (first, second))

    assertEqual = assertEquals = failUnlessEqual
    assertNotEqual = assertNotEquals = failIfEqual
    assertRaises = failUnlessRaises
    assert_ = failUnless

def isTestClass(testClass):
    return issubclass(testClass, TestCase)

def isTestCase(testCase):
    return isinstance(testCase, TestCase)

class TestSuite:
    methodPrefix = 'test'
    moduleGlob = 'test_*.py'
    
    def __init__(self):
        self.testCases = []

    def addTestCase(self, testCase):
        #print 'adding test case %s' % testCase
        methodDict = {}
        reflect.accumulateMethods(testCase, methodDict, self.methodPrefix)
        methods = methodDict.items()
        methods.sort()
        testCases = [ (testCase, method[1]) for method in methods ]
        self.testCases.extend(testCases)

    def addTestClass(self, testClass):
        #print 'adding class %s' % testClass
        testCase = testClass()
        self.addTestCase(testCase)

    def addModule(self, module):
        #print 'adding module %s' % module
        if type(module) is types.StringType:
            module = reflect.namedModule(module)
        objects = [ getattr(module, name) for name in dir(module) ]
        for name in dir(module):
            obj = getattr(module, name)
            if type(obj) is types.ClassType and isTestClass(obj):
                self.addTestClass(obj)

    def addPackage(self, packageName):
        #print 'adding package %s' % packageName
        package = reflect.namedModule(packageName)
        modGlob = os.path.join(os.path.dirname(package.__file__), self.moduleGlob)
        modules = map(reflect.filenameToModuleName, glob.glob(modGlob))
        for module in modules:
            self.addModule(module)

    def run(self, output):
#        print 'running tests'
        output.start(len(self.testCases))
        for testCase, method in self.testCases:
#            print 'testing %s %s' % (testCase, method.__name__)
            try:
#                print '  setUp()'
                testCase.setUp()
#                print '  %s' % method.__name__
                method()
#                print '  tearDown()' 
                testCase.tearDown()
#                print '  done.'
            except AssertionError, e:
                output.reportFailure(testCase, method, sys.exc_info())
            except KeyError:
                break
            except:
                output.reportError(testCase, method, sys.exc_info())
            else:
                output.reportSuccess(testCase, method)
        output.stop()

class Reporter:
    def __init__(self):
        self.errors = []
        self.failures = []
        self.numTests = 0
        self.expectedTests = 0

    def start(self, expectedTests):
        self.expectedTests = expectedTests
        self.startTime = time.time()

    def reportFailure(self, testCase, method, exc_info):
        self.failures.append((testCase, method, exc_info))
        self.numTests += 1

    def reportError(self, testCase, method, exc_info):
        self.errors.append((testCase, method, exc_info))
        self.numTests += 1

    def reportSuccess(self, testCase, method):
        self.numTests += 1

    def getRunningTime(self):
        if hasattr(self, 'stopTime'):
            return self.stopTime - self.startTime
        else:
            return time.time() - self.startTime

    def allPassed(self):
        return not (self.errors or self.failures)

    def stop(self):
        self.stopTime = time.time()

class TextReporter(Reporter):
    SEPARATOR = '-' * 79
    DOUBLE_SEPARATOR = '=' * 79
    
    def __init__(self, stream=sys.stdout):
        self.stream = stream
        Reporter.__init__(self)

    def reportFailure(self, testCase, method, exc_info):
        self.write('F')
        Reporter.reportFailure(self, testCase, method, exc_info)

    def reportError(self, testCase, method, exc_info):
        self.write('E')
        Reporter.reportError(self, testCase, method, exc_info)

    def reportSuccess(self, testCase, method):
        self.write('.')
        Reporter.reportSuccess(self, testCase, method)

    def _formatError(self, flavor, (testCase, method, error)):
        ret = ("%s\n%s: %s (%s)\n%s\n%s" %
               (self.DOUBLE_SEPARATOR,
                flavor, method.__name__, testCase.__class__,
                self.SEPARATOR,
                string.join(apply(traceback.format_exception, error))))
        return ret

    def write(self, format, *args):
        self.stream.write(format % args)
        self.stream.flush()

    def writeln(self, format=None, *args):
        if format is not None:
            self.stream.write(format % args)
        self.stream.write('\n')
        self.stream.flush()

    def _statusReport(self):
        if not (self.failures or self.errors):
            status = 'OK'
            summary = ''
        else:
            status = 'FAILED'
            if self.failures and self.errors:
                summary = '(failures=%d, errors=%d)' % (len(self.failures), len(self.errors))
            elif self.failures:
                summary = '(failures=%d)'  % (len(self.failures),)
            else:
                summary = '(errors=%d)' % (len(self.errors),)
        return '%s %s' % (status, summary)
            
    def stop(self):
        Reporter.stop(self)
        self.writeln()
        for error in self.failures:
            self.write(self._formatError('FAILURE', error))
        for error in self.errors:
            self.write(self._formatError('ERROR', error))
        self.writeln(self.SEPARATOR)
        self.writeln('Ran %d tests in %.3fs', self.numTests, self.getRunningTime())
        self.writeln()
        self.writeln(self._statusReport())


if __name__ == '__main__':
    ts = TestSuite()
    ts.addPackage('twisted.test')
    ts.run(TextReporter())
