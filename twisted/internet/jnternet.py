
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
from twisted.protocols import protocol
from twisted.persisted import styles
from twisted.python import timeoutqueue

# Java Imports
from java.net import Socket, ServerSocket, SocketException
import jarray

# System Imports
import threading, Queue, time

# Sibling Imports
import abstract


class JConnection(abstract.FileDescriptor,
                  protocol.Transport,
                  styles.Ephemeral):

    writeBlocker = None
    def __init__(self, skt, protocol):
        # print 'made a connection'
        self.skt = skt
        self.protocol = protocol
        self.istream = skt.getInputStream()
        self.ostream = skt.getOutputStream()
        self.writeQ = Queue.Queue()

    def write(self, data):
        # print 'waiting to put some data into the writeQ'
        self.writeQ.put(data)
        # print 'put data'

    def registerProducer(self, producer, streaming):
        abstract.FileDescriptor.registerProducer(self, producer, streaming)
        self.writeQ.put(BEGIN_CONSUMING)

    def unregisterProducer(self):
        abstract.FileDescriptor.unregisterProducer(self)
        self.writeQ.put(END_CONSUMING)

    def produceMore(self, x):
        # print 'being asked to produce more'
        if self.producer:
            self.producer.resumeProducing()

    def connectionLost(self, arg=None):
        # print 'closing the connection'
        self.skt.close()
        self.protocol.connectionLost()

    def loseConnection(self):
        self.writeQ.put(None)

class Blocker:
    stopped = 0
    def __init__(self, q):
        self.q = q

    def block(self):
        raise 'hello'

    def blockForever(self):
        while not self.stopped:
            obj = self.block()
            if obj:
                self.q.put(obj)

    def start(self):
        threading.Thread(target=self.blockForever).start()

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

class ReadBlocker(Blocker):
    def __init__(self, fdes, q):
        Blocker.__init__(self, q)
        self.fdes = fdes

    def block(self):
        bytes = jarray.zeros(8192, 'b')
        l = self.fdes.istream.read(bytes)
        if l == -1:
            self.stop()
            return (self.fdes.connectionLost,0)
        return (self.fdes.protocol.dataReceived, bytes[:l].tostring())

class AcceptBlocker(Blocker):
    def __init__(self, svr, q):
        Blocker.__init__(self, q)
        self.svr = svr

    def block(self):
        skt = self.svr.sskt.accept()
        return (self.svr.gotSocket, skt)

class JMultiplexor:
    def __init__(self):
        self.readers = []
        self.writers = []
        self.q = timeoutqueue.TimeoutQueue()

    def run(self):
        while 1:
            # run the delayeds
            timeout = None
            for delayed in main.delayeds:
                delayed.runUntilCurrent()
                newTimeout = delayed.timeout()
                if ((newTimeout is not None) and
                    ((timeout is None) or
                     (newTimeout < timeout))):
                    timeout = newTimeout
            
            # wait at most `timeout` seconds for action to be added to queue
            try:
                self.q.wait(timeout)
            except timeoutqueue.TimedOut:
                pass
            
            # run actions in queue
            for i in range(self.q.qsize()):
                meth, arg = self.q.get()
                meth(arg)


theMultiplexor = JMultiplexor()

def doNothing(arg):
    pass

def wakeUp():
    theMultiplexor.q.put((doNothing, None))

def portStartListening(tcpPort):
    sskt = ServerSocket(tcpPort.port, tcpPort.backlog)
    tcpPort.sskt = sskt
    AcceptBlocker(tcpPort, theMultiplexor.q).start()

def portGotSocket(tcpPort, skt):
    # make this into an address...
    protocol = tcpPort.factory.buildProtocol(None)
    transport = JConnection(skt, protocol)
        
    # make read and write blockers
    wb = WriteBlocker(transport, theMultiplexor.q)
    wb.start()
    transport.writeBlocker = wb
    ReadBlocker(transport, theMultiplexor.q).start()
    protocol.makeConnection(transport, tcpPort)


# change port around
import tcp
tcp.Port.startListening = portStartListening
tcp.Port.gotSocket = portGotSocket

import main
main.run = theMultiplexor.run
main.wakeUp = wakeUp
