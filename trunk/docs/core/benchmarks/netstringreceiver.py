# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.test import proto_helpers, test_protocols
import math
import time
import sys
import os
import gc

NETSTRING_PREFIX_TEMPLATE ="%d:"
NETSTRING_POSTFIX = ","
USAGE = """\
Usage: %s <number> <filename>

This script creates up to 2 ** <number> chunks with up to 2 **
<number> characters and sends them to the NetstringReceiver. The
sorted performance data for all combination is written to <filename>
afterwards.

You might want to start with a small number, maybe 10 or 12, and slowly
increase it. Stop when the performance starts to deteriorate ;-).
"""

class PerformanceTester(object):
    """
    A class for testing the performance of some
    """

    headers = []
    lineFormat = ""
    performanceData = {}

    def __init__(self, filename):
        """
        Initializes C{self.filename}.

        If a file with this name already exists, asks if it should be
        overwritten. Terminates with exit status 1, if the user does
        not accept.
        """
        if os.path.isfile(filename):
            response = raw_input(("A file named %s exists. "
                                 "Overwrite it (y/n)? ") % filename)
            if response.lower() != "y":
                print "Performance test cancelled."
                sys.exit(1)
        self.filename = filename


    def testPerformance(self, number):
        """
        Drives the execution of C{performTest} with arguments between
        0 and C{number - 1}.

        @param number: Defines the number of test runs to be performed.
        @type number: C{int}
        """
        for iteration in xrange(number):
            self.performTest(iteration)


    def performTest(self, iteration):
        """
        Performs one test iteration. Overwrite this.

        @param iteration: The iteration number. Can be used to configure
            the test.
        @type iteration: C{int}
        @raise NotImplementedError: because this method has to be implemented
            by the subclass.
        """
        raise NotImplementedError


    def createReport(self):
        """
        Creates a file and writes a table with performance data.

        The performance data are ordered by the total size of the netstrings.
        In addition they show the chunk size, the number of chunks and the
        time (in seconds) that elapsed while the C{NetstringReceiver}
        received the netstring.

        @param filename: The name of the report file that will be written.
        @type filename: C{str}
        """
        self.outputFile = open(self.filename, "w")
        self.writeHeader()
        self.writePerformanceData()
        self.writeLineSeparator()
        print "The report was written to %s." % self.filename


    def writeHeader(self):
        """
        Writes the table header for the report.
        """
        self.writeLineSeparator()
        self.outputFile.write("| %s |\n" % (" | ".join(self.headers),))
        self.writeLineSeparator()


    def writeLineSeparator(self):
        """
        Writes a 'line separator' made from '+' and '-' characters.
        """
        dashes = ("-" * (len(header) + 2) for header in self.headers)
        self.outputFile.write("+%s+\n" % "+".join(dashes))


    def writePerformanceData(self):
        """
        Writes one line for each item in C{self.performanceData}.
        """
        for combination, elapsed in sorted(self.performanceData.iteritems()):
            totalSize, chunkSize, numberOfChunks = combination
            self.outputFile.write(self.lineFormat %
                                  (totalSize, chunkSize, numberOfChunks,
                                   elapsed))



class NetstringPerformanceTester(PerformanceTester):
    """
    A class for determining the C{NetstringReceiver.dataReceived} performance.

    Instantiates a C{NetstringReceiver} and calls its
    C{dataReceived()} method with different chunks sizes and numbers
    of chunks.  Presents a table showing the relation between input
    data and time to process them.
    """

    headers = ["Chunk size", "Number of chunks", "Total size",
               "Time to receive" ]
    lineFormat = ("| %%%dd | %%%dd | %%%dd | %%%d.4f |\n" %
                  tuple([len(header) for header in headers]))

    def __init__(self, filename):
        """
        Sets up the output file and the netstring receiver that will be
        used for receiving data.

        @param filename: The name of the file for storing the report.
        @type filename: C{str}
        """
        PerformanceTester.__init__(self, filename)
        transport = proto_helpers.StringTransport()
        self.netstringReceiver = test_protocols.TestNetstring()
        self.netstringReceiver.makeConnection(transport)


    def performTest(self, number):
        """
        Tests the performance of C{NetstringReceiver.dataReceived}.

        Feeds netstrings of various sizes in different chunk sizes
        to a C{NetstringReceiver} and stores the elapsed time in
        C{self.performanceData}.

        @param number: The maximal chunks size / number of
            chunks to be checked.
        @type number: C{int}
        """
        chunkSize = 2 ** number
        numberOfChunks = chunkSize
        while numberOfChunks:
            self.testCombination(chunkSize, numberOfChunks)
            numberOfChunks = numberOfChunks // 2


    def testCombination(self, chunkSize, numberOfChunks):
        """
        Tests one combination of chunk size and number of chunks.

        @param chunkSize: The size of one chunk to be sent to the
            C{NetstringReceiver}.
        @type chunkSize: C{int}
        @param numberOfChunks: The number of C{chunkSize}-sized chunks to
            be sent to the C{NetstringReceiver}.
        @type numberOfChunks: C{int}
        """
        chunk, dataSize = self.configureCombination(chunkSize, numberOfChunks)
        elapsed = self.receiveData(chunk, numberOfChunks, dataSize)
        key = (chunkSize, numberOfChunks, dataSize)
        self.performanceData[key] = elapsed


    def configureCombination(self, chunkSize, numberOfChunks):
        """
        Updates C{MAX_LENGTH} for {self.netstringReceiver} (to avoid
        C{NetstringParseErrors} that might be raised if the size
        exceeds the default C{MAX_LENGTH}).

        Calculates and returns one 'chunk' of data and the total size
        of the netstring.

        @param chunkSize: The size of chunks that will be received.
        @type chunkSize: C{int}
        @param numberOfChunks: The number of C{chunkSize}-sized chunks
            that will be received.
        @type numberOfChunks: C{int}

        @return: A tuple consisting of string of C{chunkSize} 'a'
        characters and the size of the netstring data portion.
        """
        chunk = "a" * chunkSize
        dataSize = chunkSize * numberOfChunks
        self.netstringReceiver.MAX_LENGTH = dataSize
        numberOfDigits = math.ceil(math.log10(dataSize)) + 1
        return chunk, dataSize


    def receiveData(self, chunk, numberOfChunks, dataSize):
        dr = self.netstringReceiver.dataReceived
        now = time.time()
        dr(NETSTRING_PREFIX_TEMPLATE % (dataSize,))
        for idx in xrange(numberOfChunks):
            dr(chunk)
        dr(NETSTRING_POSTFIX)
        elapsed = time.time() - now
        assert self.netstringReceiver.received, "Didn't receive string!"
        return elapsed


def disableGarbageCollector():
    gc.disable()
    print 'Disabled Garbage Collector.'


def main(number, filename):
    disableGarbageCollector()
    npt = NetstringPerformanceTester(filename)
    npt.testPerformance(int(number))
    npt.createReport()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print USAGE % sys.argv[0]
        sys.exit(1)
    main(*sys.argv[1:3])
