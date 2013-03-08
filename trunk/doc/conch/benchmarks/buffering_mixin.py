# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Benchmarks comparing the write performance of a "normal" Protocol instance
and an instance of a Protocol class which has had L{twisted.conch.mixin}'s
L{BufferingMixin<twisted.conch.mixin.BufferingMixin>} mixed in to perform
Nagle-like write coalescing.
"""

from sys import stdout
from pprint import pprint
from time import time

from twisted.python.usage import Options
from twisted.python.log import startLogging

from twisted.internet.protocol import ServerFactory, Protocol, ClientCreator
from twisted.internet.defer import Deferred
from twisted.internet import reactor

from twisted.conch.mixin import BufferingMixin


class BufferingBenchmark(Options):
    """
    Options for configuring the execution parameters of a benchmark run.
    """

    optParameters = [
        ('scale', 's', '1',
         'Work multiplier (bigger takes longer, might resist noise better)')]

    def postOptions(self):
        self['scale'] = int(self['scale'])



class ServerProtocol(Protocol):
    """
    A silent protocol which only waits for a particular amount of input and
    then fires a Deferred.
    """
    def __init__(self, expected, finished):
        self.expected = expected
        self.finished = finished


    def dataReceived(self, bytes):
        self.expected -= len(bytes)
        if self.expected == 0:
            finished, self.finished = self.finished, None
            finished.callback(None)



class BufferingProtocol(Protocol, BufferingMixin):
    """
    A protocol which uses the buffering mixin to provide a write method.
    """



class UnbufferingProtocol(Protocol):
    """
    A protocol which provides a naive write method which simply passes through
    to the transport.
    """

    def connectionMade(self):
        """
        Bind write to the transport's write method and flush to a no-op
        function in order to provide the same API as is provided by
        BufferingProtocol.
        """
        self.write = self.transport.write
        self.flush = lambda: None



def _write(proto, byteCount):
    write = proto.write
    flush = proto.flush

    for i in range(byteCount):
        write('x')
    flush()



def _benchmark(byteCount, clientProtocol):
    result = {}
    finished = Deferred()
    def cbFinished(ignored):
        result[u'disconnected'] = time()
        result[u'duration'] = result[u'disconnected'] - result[u'connected']
        return result
    finished.addCallback(cbFinished)

    f = ServerFactory()
    f.protocol = lambda: ServerProtocol(byteCount, finished)
    server = reactor.listenTCP(0, f)

    f2 = ClientCreator(reactor, clientProtocol)
    proto = f2.connectTCP('127.0.0.1', server.getHost().port)
    def connected(proto):
        result[u'connected'] = time()
        return proto
    proto.addCallback(connected)
    proto.addCallback(_write, byteCount)
    return finished



def _benchmarkBuffered(byteCount):
    return _benchmark(byteCount, BufferingProtocol)



def _benchmarkUnbuffered(byteCount):
    return _benchmark(byteCount, UnbufferingProtocol)



def benchmark(scale=1):
    """
    Benchmark and return information regarding the relative performance of a
    protocol which does not use the buffering mixin and a protocol which
    does.

    @type scale: C{int}
    @param scale: A multipler to the amount of work to perform

    @return: A Deferred which will fire with a dictionary mapping each of
    the two unicode strings C{u'buffered'} and C{u'unbuffered'} to
    dictionaries describing the performance of a protocol of each type. 
    These value dictionaries will map the unicode strings C{u'connected'}
    and C{u'disconnected'} to the times at which each of those events
    occurred and C{u'duration'} two the difference between these two values.
    """
    overallResult = {}

    byteCount = 1024

    bufferedDeferred = _benchmarkBuffered(byteCount * scale)
    def didBuffered(bufferedResult):
        overallResult[u'buffered'] = bufferedResult
        unbufferedDeferred =  _benchmarkUnbuffered(byteCount * scale)
        def didUnbuffered(unbufferedResult):
            overallResult[u'unbuffered'] = unbufferedResult
            return overallResult
        unbufferedDeferred.addCallback(didUnbuffered)
        return unbufferedDeferred
    bufferedDeferred.addCallback(didBuffered)
    return bufferedDeferred



def main(args=None):
    """
    Perform a single benchmark run, starting and stopping the reactor and
    logging system as necessary.
    """
    startLogging(stdout)

    options = BufferingBenchmark()
    options.parseOptions(args)

    d = benchmark(options['scale'])
    def cbBenchmark(result):
        pprint(result)
    def ebBenchmark(err):
        print err.getTraceback()
    d.addCallbacks(cbBenchmark, ebBenchmark)
    def stopReactor(ign):
        reactor.stop()
    d.addBoth(stopReactor)
    reactor.run()


if __name__ == '__main__':
    main()
