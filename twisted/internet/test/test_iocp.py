from twisted.trial import unittest

try:
    from twisted.internet.iocpreactor import iocpsupport as _iocp, tcp, udp
    from twisted.internet.iocpreactor.reactor import IOCPReactor, EVENTS_PER_LOOP, KEY_NORMAL
    from twisted.internet.iocpreactor.interfaces import IReadWriteHandle
except ImportError:
    skip = 'This test only applies to IOCPReactor'

from zope.interface.verify import verifyClass

class IOCPReactorTestCase(unittest.TestCase):
    def test_noPendingTimerEvents(self):
        """
        Test reactor behavior (doIteration) when there are no pending time
        events.
        """
        ir = IOCPReactor()
        ir.wakeUp()
        self.failIf(ir.doIteration(None))


    def test_reactorInterfaces(self):
        """
        Verify that IOCP socket-representing classes implement IReadWriteHandle
        """
        verifyClass(IReadWriteHandle, tcp.Connection)
        verifyClass(IReadWriteHandle, udp.Port)


    def test_maxEventsPerIteration(self):
        """
        Verify that we don't lose an event when more than EVENTS_PER_LOOP
        events occur in the same reactor iteration
        """
        class FakeFD:
            counter = 0
            def logPrefix(self):
                return 'FakeFD'
            def cb(self, rc, bytes, evt):
                self.counter += 1

        ir = IOCPReactor()
        fd = FakeFD()
        event = _iocp.Event(fd.cb, fd)
        for _ in range(EVENTS_PER_LOOP + 1):
            ir.port.postEvent(0, KEY_NORMAL, event)
        ir.doIteration(None)
        self.assertEquals(fd.counter, EVENTS_PER_LOOP)
        ir.doIteration(0)
        self.assertEquals(fd.counter, EVENTS_PER_LOOP + 1)

