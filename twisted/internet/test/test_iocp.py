from twisted.internet.protocol import ServerFactory, Protocol, ClientCreator
from twisted.internet.defer import DeferredList, maybeDeferred, Deferred
from twisted.trial import unittest
from twisted.internet import reactor
from twisted.python import log

from zope.interface.verify import verifyClass

class StopStartReadingProtocol(Protocol):
    def connectionMade(self):
        self.transport.pauseProducing()
        self.transport.resumeProducing()
        reactor.callLater(0, self._beTerrible)
        self.data = ''


    def _beTerrible(self):
        self.transport.pauseProducing()
        self.transport.resumeProducing()
        reactor.callLater(0, self._beMoreTerrible)


    def _beMoreTerrible(self):
        self.transport.pauseProducing()
        self.transport.resumeProducing()
        reactor.callLater(0, self.factory.ready_d.callback, self)


    def dataReceived(self, data):
        log.msg('got data', len(data))
        self.data += data
        if len(self.data) == 4*self.transport.readBufferSize:
            self.factory.stop_d.callback(self.data)



class IOCPReactorTestCase(unittest.TestCase):
    def test_noPendingTimerEvents(self):
        """
        Test reactor behavior (doIteration) when there are no pending time
        events.
        """
        from twisted.internet.iocpreactor.reactor import IOCPReactor
        ir = IOCPReactor()
        ir.wakeUp()
        self.failIf(ir.doIteration(None))


    def test_stopStartReading(self):
        """
        This test checks transport read state! There are three bits
        of it:
        1) The transport producer is paused -- transport.reading
           is False)
        2) The transport is about to schedule an OS read, on the next
           reactor iteration -- transport._readScheduled
        3) The OS has a pending asynchronous read on our behalf --
           transport._readScheduledInOS
        if 3) is not implemented, it is possible to trick IOCPReactor into
        scheduling an OS read before the previous one finishes
        """
        sf = ServerFactory()
        sf.protocol = StopStartReadingProtocol
        sf.ready_d = Deferred()
        sf.stop_d = Deferred()
        p = reactor.listenTCP(0, sf)
        port = p.getHost().port
        cc = ClientCreator(reactor, Protocol)
        def proceed(protos, port):
            log.msg('PROCEEDING WITH THE TESTATHRON')
            self.assert_(protos[0])
            self.assert_(protos[1])
            protos = protos[0][1], protos[1][1]
            protos[0].transport.write(
                    'x' * (2 * protos[0].transport.readBufferSize) +
                    'y' * (2 * protos[0].transport.readBufferSize))
            return sf.stop_d.addCallback(cleanup, protos, port)
        
        def cleanup(data, protos, port):
            self.assert_(data == 'x'*(2*protos[0].transport.readBufferSize)+
                                 'y'*(2*protos[0].transport.readBufferSize),
                                 'did not get the right data')
            return DeferredList([
                    maybeDeferred(protos[0].transport.loseConnection),
                    maybeDeferred(protos[1].transport.loseConnection),
                    maybeDeferred(port.stopListening)])

        return (DeferredList([cc.connectTCP('127.0.0.1', port), sf.ready_d])
                .addCallback(proceed, p))


    def test_reactorInterfaces(self):
        """
        Verify that IOCP socket-representing classes implement IReadWriteHandle
        """
        from twisted.internet.iocpreactor.interfaces import IReadWriteHandle
        from twisted.internet.iocpreactor import tcp, udp
        verifyClass(IReadWriteHandle, tcp.Connection)
        verifyClass(IReadWriteHandle, udp.Port)



if reactor.__class__.__name__ != 'IOCPReactor':
    IOCPReactorTestCase.skip = 'This test only applies to IOCPReactor'

