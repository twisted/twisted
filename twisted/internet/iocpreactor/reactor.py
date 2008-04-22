# -*- test-case-name: twisted.internet.test.test_iocp -*-

# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Reactor that uses IO completion ports
"""


from twisted.internet import base, interfaces, main, error
from twisted.python import log, failure
from twisted.internet._dumbwin32proc import Process

from zope.interface import implements
import socket, sys

from twisted.internet.iocpreactor import iocpsupport as _iocp
from twisted.internet.iocpreactor.const import WAIT_TIMEOUT
from twisted.internet.iocpreactor import tcp, udp

from twisted.python.compat import set

MAX_TIMEOUT = 2000 # 2 seconds, see doIteration for explanation

EVENTS_PER_LOOP = 1000 # XXX: what's a good value here?

# keys to associate with normal and waker events
KEY_NORMAL, KEY_WAKEUP = range(2)

_NO_GETHANDLE = error.ConnectionFdescWentAway(
                    'Handler has no getFileHandle method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')



class IOCPReactor(base._SignalReactorMixin, base.ReactorBase):
    implements(interfaces.IReactorTCP, interfaces.IReactorUDP,
               interfaces.IReactorMulticast, interfaces.IReactorProcess)

    port = None

    def __init__(self):
        base.ReactorBase.__init__(self)
        self.port = _iocp.CompletionPort()
        self.handles = set()


    def addActiveHandle(self, handle):
        self.handles.add(handle)


    def removeActiveHandle(self, handle):
        self.handles.discard(handle)


    def doIteration(self, timeout):
        # This function sits and waits for an IO completion event.
        #
        # There are two requirements: process IO events as soon as they arrive
        # and process ctrl-break from the user in a reasonable amount of time.
        #
        # There are three kinds of waiting.
        # 1) GetQueuedCompletionStatus (self.port.getEvent) to wait for IO
        # events only.
        # 2) Msg* family of wait functions that can stop waiting when
        # ctrl-break is detected (then, I think, Python converts it into a
        # KeyboardInterrupt)
        # 3) *Ex family of wait functions that put the thread into an
        # "alertable" wait state which is supposedly triggered by IO completion
        #
        # 2) and 3) can be combined. Trouble is, my IO completion is not
        # causing 3) to trigger, possibly because I do not use an IO completion
        # callback. Windows is weird.
        # There are two ways to handle this. I could use MsgWaitForSingleObject
        # here and GetQueuedCompletionStatus in a thread. Or I could poll with
        # a reasonable interval. Guess what! Threads are hard.

        processed_events = 0
        if timeout is None:
            timeout = MAX_TIMEOUT
        else:
            timeout = min(MAX_TIMEOUT, int(1000*timeout))
        rc, bytes, key, evt = self.port.getEvent(timeout)
        while processed_events < EVENTS_PER_LOOP:
            if rc == WAIT_TIMEOUT:
                break
            if key != KEY_WAKEUP:
                assert key == KEY_NORMAL
                if not evt.ignore:
                    log.callWithLogger(evt.owner, self._callEventCallback,
                                       rc, bytes, evt)
                    processed_events += 1
            rc, bytes, key, evt = self.port.getEvent(0)


    def _callEventCallback(self, rc, bytes, evt):
        owner = evt.owner
        why = None
        try:
            evt.callback(rc, bytes, evt)
            handfn = getattr(owner, 'getFileHandle', None)
            if not handfn:
                why = _NO_GETHANDLE
            elif handfn() == -1:
                why = _NO_FILEDESC
            if why:
                return # ignore handles that were closed
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            owner.loseConnection(failure.Failure(why))


    def installWaker(self):
        pass


    def wakeUp(self):
        self.port.postEvent(0, KEY_WAKEUP, None)


    def registerHandle(self, handle):
        self.port.addHandle(handle, KEY_NORMAL)


    def createSocket(self, af, stype):
        skt = socket.socket(af, stype)
        self.registerHandle(skt.fileno())
        return skt


    def listenTCP(self, port, factory, backlog=50, interface=''):
        """
        @see: twisted.internet.interfaces.IReactorTCP.listenTCP
        """
        p = tcp.Port(port, factory, backlog, interface, self)
        p.startListening()
        return p


    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """
        @see: twisted.internet.interfaces.IReactorTCP.connectTCP
        """
        c = tcp.Connector(host, port, factory, timeout, bindAddress, self)
        c.connect()
        return c


    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        """
        Connects a given L{DatagramProtocol} to the given numeric UDP port.

        @returns: object conforming to L{IListeningPort}.
        """
        p = udp.Port(port, protocol, interface, maxPacketSize, self)
        p.startListening()
        return p


    def listenMulticast(self, port, protocol, interface='', maxPacketSize=8192,
                        listenMultiple=False):
        """
        Connects a given DatagramProtocol to the given numeric UDP port.

        EXPERIMENTAL.

        @returns: object conforming to IListeningPort.
        """
        p = udp.MulticastPort(port, protocol, interface, maxPacketSize, self,
                              listenMultiple)
        p.startListening()
        return p


    def spawnProcess(self, processProtocol, executable, args=(), env={},
                     path=None, uid=None, gid=None, usePTY=0, childFDs=None):
        """
        Spawn a process.
        """
        if uid is not None:
            raise ValueError("Setting UID is unsupported on this platform.")
        if gid is not None:
            raise ValueError("Setting GID is unsupported on this platform.")
        if usePTY:
            raise ValueError("PTYs are unsupported on this platform.")
        if childFDs is not None:
            raise ValueError(
                "Custom child file descriptor mappings are unsupported on "
                "this platform.")
        args, env = self._checkProcessArgs(args, env)
        return Process(self, processProtocol, executable, args, env, path)


    def removeAll(self):
        res = list(self.handles)
        self.handles.clear()
        return res



def install():
    r = IOCPReactor()
    main.installReactor(r)


__all__ = ['IOCPReactor', 'install']

