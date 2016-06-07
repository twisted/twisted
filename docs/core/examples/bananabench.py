# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python import compat
import sys
import time
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
    
# Twisted Imports
from twisted.spread import banana
from twisted.internet import protocol

iterationCount = 10000

class BananaBench:
    r = range( iterationCount )
    def setUp(self, encClass):
        self.io = StringIO.StringIO()
        self.enc = encClass()
        self.enc.makeConnection(protocol.FileWrapper(self.io))
        self.enc._selectDialect("none")
        self.enc.expressionReceived = self.putResult

    def putResult(self, result):
        self.result = result

    def tearDown(self):
        self.enc.connectionLost()
        del self.enc

    def testEncode(self, value):
        starttime = time.time()
        for i in self.r:
            self.enc.sendEncoded(value)
            self.io.truncate(0)
        endtime = time.time()
        print '    Encode took %s seconds' % (endtime - starttime)
        return endtime - starttime

    def testDecode(self, value):
        self.enc.sendEncoded(value)
        encoded = self.io.getvalue()
        starttime = time.time()
        for i in self.r:
            self.enc.dataReceived(encoded)
        endtime = time.time()
        print '    Decode took %s seconds' % (endtime - starttime)
        return endtime - starttime

    def performTest(self, method, data, encClass):
        self.setUp(encClass)
        method(data)
        self.tearDown()

    def runTests(self, testData):
        print 'Test data is: %s' % testData
        print '  Using Pure Python Banana:'
        self.performTest(self.testEncode, testData, banana.Banana)
        self.performTest(self.testDecode, testData, banana.Banana)

bench = BananaBench()
print 'Doing %s iterations of each test.' % iterationCount
print ''
testData = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
bench.runTests(testData)
testData = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
bench.runTests(testData)
testData = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
bench.runTests(testData)
testData = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
bench.runTests(testData)
testData = [compat.long(1), compat.long(2), compat.long(3), compat.long(4), compat.long(5), compat.long(6),
            compat.long(7), compat.long(8), compat.long(9), compat.long(10)]
bench.runTests(testData)
testData = [1, 2, [3, 4], [30.5, 40.2], 5, ["six", "seven", ["eight", 9]], [10], []]
bench.runTests(testData)

