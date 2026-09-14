# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import time
from io import BytesIO

from twisted.internet import protocol

# Twisted Imports
from twisted.spread import banana

iterationCount = 10000


class BananaBench:
    r = range(iterationCount)

    def setUp(self, encClass):
        self.io = BytesIO()
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
        print(f"    Encode took {endtime - starttime} seconds")
        return endtime - starttime

    def testDecode(self, value):
        self.enc.sendEncoded(value)
        encoded = self.io.getvalue()
        starttime = time.time()
        for i in self.r:
            self.enc.dataReceived(encoded)
        endtime = time.time()
        print(f"    Decode took {endtime - starttime} seconds")
        return endtime - starttime

    def performTest(self, method, data, encClass):
        self.setUp(encClass)
        method(data)
        self.tearDown()

    def runTests(self, testData):
        print(f"Test data is: {testData}")
        print("  Using Pure Python Banana:")
        self.performTest(self.testEncode, testData, banana.Banana)
        self.performTest(self.testDecode, testData, banana.Banana)


bench = BananaBench()
print(f"Doing {iterationCount} iterations of each test.")
print("")
testData = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
bench.runTests(testData)
testData = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
bench.runTests(testData)
testData = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
bench.runTests(testData)
testData = [
    b"one",
    b"two",
    b"three",
    b"four",
    b"five",
    b"six",
    b"seven",
    b"eight",
    b"nine",
    b"ten",
]
bench.runTests(testData)
testData = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
bench.runTests(testData)
testData = [1, 2, [3, 4], [30.5, 40.2], 5, [b"six", b"seven", [b"eight", 9]], [10], []]
bench.runTests(testData)
