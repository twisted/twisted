
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""A java implementation of a ``select'' loop.
"""

# Twisted Imports
from twisted.internet import protocol
from twisted.persisted import styles
from twisted.python import timeoutqueue, log

# Java Imports
from java.net import Socket, ServerSocket, SocketException, InetAddress
import java.io.InterruptedIOException
import java.io.IOException
from java.lang import System
import jarray

# System Imports
import threading, Queue, time

# Sibling Imports
import abstract
import interfaces
from twisted.internet.base import ReactorBase


class JConnection(abstract.FileDescriptor,
                  styles.Ephemeral):
    """A java connection class."""

    writeBlocker = None

    def __init__(self, skt, protocol, jport):
        self.skt = skt
        self.protocol = protocol
        self.istream = skt.getInputStream()
        self.ostream = skt.getOutputStream()
        self.writeQ = Queue.Queue()
        self.jport = jport

    def write(self, data):
        self.writeQ.put(data)

    def registerProducer(self, producer, streaming):
        abstract.FileDescriptor.registerProducer(self, producer, streaming)
        self.writeQ.put(BEGIN_CONSUMING)

    def unregisterProducer(self):
        abstract.FileDescriptor.unregisterProducer(self)
        self.writeQ.put(END_CONSUMING)

    def produceMore(self, x):
        if self.producer:
            self.producer.resumeProducing()

    def connectionLost(self, arg=None):
        if not self.disconnected:
            self.disconnected = 1
            self.skt.shutdownInput()
            self.skt.shutdownOutput()
            self.skt.close()
            self.protocol.connectionLost(arg)
            abstract.FileDescriptor.connectionLost(self, arg)

    def loseConnection(self):
        self.disconnecting = 1
        self.writeQ.put(None)

    def getHost(self):
        # addr = self.skt.getInetAddress()
        return ('INET', InetAddress.getLocalHost().getHostAddress(), self.jport.port)

    def getPeer(self):
        addr = self.skt.getInetAddress()
        return ('INET', addr.getHostAddress(), self.skt.getPort())

    def getTcpNoDelay(self):
        return self.skt.getTcpNoDelay()

    def setTcpNoDelay(self, enabled):
        self.skt.setTcpNoDelay(enabled)


class Blocker(threading.Thread):

    stopped = 0

    def __init__(self, q):
        threading.Thread.__init__(self)
        self.q = q

    def block(self):
        raise 'hello'

    def blockForever(self):
        while not self.stopped:
            obj = self.block()
            if obj:
                self.q.put(obj)
        self.q.put((self.blockerFinished, None))

    def blockerFinished(self, ignore):
        """Called in main thread when blocker finishes."""
        pass

    def run(self):
        self.blockForever()

    def stop(self):
        self.stopped = 1

BEGIN_CONSUMING = 1
END_CONSUMING = 2

class WriteBlocker(Blocker):

    def __init__(self, fdes, q):
        Blocker.__init__(self, q)
        self.fdes = fdes
        self.consuming = 0

    def block(self):
        if self.consuming:
            try:
                data = self.fdes.writeQ.get_nowait()
            except Queue.Empty:
                self.producing = 0
                self.q.put((self.fdes.produceMore, 1))
                data = self.fdes.writeQ.get()
        else:
            data = self.fdes.writeQ.get()
        if data is None:
            self.stop()
            return (self.fdes.connectionLost, None)
        elif data == BEGIN_CONSUMING:
            self.consuming = 1
        elif data == END_CONSUMING:
            self.consuming = 0
        else:
            # bytes = jarray.array(map(ord, data), 'b')
            try:
                self.fdes.ostream.write(data)
                self.fdes.ostream.flush()
            except SocketException:
                self.stop()
                return (self.fdes.connectionLost, None)


class ReadBlocker(Blocker):

    def __init__(self, fdes, q):
        Blocker.__init__(self, q)
        self.fdes = fdes

    def block(self):
        bytes = jarray.zeros(8192, 'b')
        try:
            l = self.fdes.istream.read(bytes)
        except SocketException:
            self.stop()
            return (self.fdes.connectionLost, 0)
        if l == -1:
            self.stop()
            return (self.fdes.connectionLost, 0)
        return (self.fdes.protocol.dataReceived, bytes[:l].tostring())


class AcceptBlocker(Blocker):

    def __init__(self, svr, q):
        Blocker.__init__(self, q)
        self.svr = svr

    def block(self):
        while 1:
            try:
                skt = self.svr.sskt.accept()
                return (self.svr.gotSocket, skt)
            except (java.io.InterruptedIOException, java.io.IOException):
                if not self.svr.isListening:
                    self.svr.sskt.close()
                    return


class JReactor(ReactorBase):
    """Fakes multiplexing using multiple threads and an action queue."""

    def __init__(self):
        ReactorBase.__init__(self)
        self.readers = []
        self.writers = []
        self.q = timeoutqueue.TimeoutQueue()

    def installWaker(self):
        pass

    def wakeUp(self):
        self.q.put(lambda x: x, None)
    
    def run(self, **kwargs):
        import main
        main.running = 1

        while 1:
            # run the delayeds
            self.runUntilCurrent()
            timeout = self.timeout()
            if timeout is None:
                timeout = 1.0
            
            self.doIteration(timeout)

    def doIteration(self, timeout):
        # wait at most `timeout` seconds for action to be added to queue
        try:
            self.q.wait(timeout)
        except timeoutqueue.TimedOut:
            pass

        # run actions in queue
        for i in range(self.q.qsize()):
            meth, arg = self.q.get()
            meth(arg)


    def listenTCP(self, port, factory, backlog=5, interface=''):
        jp = JavaPort(self, port, factory, backlog)
        jp.startListening()
        return jp

    def wakeUp(self):
        self.q.put((doNothing, None))


def doNothing(arg):
    pass


class JavaPort:
    __implements__ = interfaces.IListeningPort

    def __init__(self, reactor, port, factory, backlog):
        self.reactor = reactor
        self.factory = factory
        self.port = port
        self.backlog = backlog
        self.isListening = 1

    def startListening(self):
        self.factory.doStart()
        sskt = ServerSocket(self.port, self.backlog)
        sskt.setSoTimeout(100)
        self.sskt = sskt
        AcceptBlocker(self, self.reactor.q).start()
        log.msg("%s starting on %s"%(self.factory.__class__, self.port))

    def stopListening(self):
        self.isListening = 0

    def blockerFinished(self, ignore):
        """Called when AcceptBlocker is finished."""
        self.factory.doStop()

    def gotSocket(self, skt):
        # make this into an address...
        protocol = self.factory.buildProtocol(None)
        transport = JConnection(skt, protocol, self)

        # make read and write blockers
        protocol.makeConnection(transport)
        wb = WriteBlocker(transport, self.reactor.q)
        wb.start()
        transport.writeBlocker = wb
        ReadBlocker(transport, self.reactor.q).start()


class Errno:
    """A class which will pretend to be a module."""

    def __getattr__(self, name):
        return 1


def install():
    # jython has no errno module, so we fake it
    import sys
    sys.modules["errno"] = Errno()
    reactor = JReactor()
    import main
    main.installReactor(reactor)
    return reactor
