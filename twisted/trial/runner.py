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

import types 
from twisted.python import components, reflect, log, context

class ITestRunner(components.Interface):
    def getTestClass(self):
        pass
    
    def getMethods(self):
        pass

    def numTests(self):
        pass

    def runTest(self, method):
        pass

    def runTests(self, output):
        pass


class SingletonRunner:
    __implements__ = (ITestRunner,)
    def __init__(self, methodName):
        if type(methodName) is types.StringType:
            self.testClass = reflect.namedObject('.'.join(methodName.split('.')[:-1]))
            self.methodName = methodName.split('.')[-1]
        else:
            self.testClass = methodName.im_class
            self.methodName = methodName.__name__

    def __str__(self):
        return "%s.%s.%s" % (self.testClass.__module__, self.testClass.__name__,
                             self.methodName)

    def getMethods(self):
        return [ self.methodName ]

    def numTests(self):
        return 1

    def runTest(self, method):
        assert method.__name__ == self.methodName
        method()

    def runTests(self, output):
        testCase = self.testClass()
        testCase.setUpClass()
        method = getattr(testCase, self.methodName)
        output.reportStart(self.testClass, method)
        tester = unittest.Tester(self.testClass, testCase, method, self.runTest)
        results = tester.run()
        output.reportResults(self.testClass, method, *results)
        testCase.tearDownClass()


class TestClassRunner:
    __implements__ = (ITestRunner,)
    methodPrefixes = ('test',)
    
    def __init__(self, testClass, stats=None):
        self.testClass = testClass
        self.methodNames = []
        for prefix in self.methodPrefixes:
            self.methodNames.extend([ "%s%s" % (prefix, name) for name in
                                      reflect.prefixedMethodNames(testClass, prefix)])
        # N.B.: --random will shuffle testClasses but not our methodNames[]
        self.methodNames.sort()
        if stats is not None:
            self.stats = stats
            
    def __str__(self):
        return "%s.%s" % (self.testClass.__module__, self.testClass.__name__)

    def getTestClass(self):
        return self.testClass

    def getMethods(self):
        return self.methodNames

    def numTests(self):
        return len(self.methodNames)

    def runTest(self, method):
        assert method.__name__ in self.methodNames, "Method %s is not a test method!" % (method.__name__,)
        method()

    def runTests(self, output):
        self.testCase = self.testClass()
        self.testCase._resultReporter_ = output
        self.testCase.setUpClass()
        for methodName in self.methodNames:
            log.msg("--> %s.%s <--" % (self.testCase.__class__, methodName))
            method = getattr(self.testCase, methodName)
            output.reportStart(self.testClass, method)
            results = unittest.Tester(self.testClass, self.testCase,
                                      method, self.runTest).run()
            output.reportResults(self.testClass, method, *results)
        self.testCase.tearDownClass()

def runTest(method):
    # utility function, used by test_trial to more closely emulate the usual
    # testing process. This matches the same check in util.extract_tb that
    # matches SingletonRunner.runTest and TestClassRunner.runTest .
    method()


class PerformanceTestClassRunner(TestClassRunner):
    methodPrefixes = ('benchmark',)

    def runTest(self, method):
        assert method.__name__ in self.methodNames
        fullName = "%s.%s" % (method.im_class, method.im_func.__name__)
        method.im_self.recordStat = lambda datum: self.stats.__setitem__(fullName,datum)
        method()


class PerformanceSingletonRunner(SingletonRunner):

    def __init__(self, methodName, stats):
        SingletonRunner.__init__(self, methodName)
        self.stats = stats

    def runTest(self, method):
        assert method.__name__ == self.methodName
        fullName = "%s.%s" % (method.im_class, method.im_func.__name__)
        method.im_self.recordStat = lambda datum: self.stats.__setitem__(fullName, datum)
        method()




import unittest
