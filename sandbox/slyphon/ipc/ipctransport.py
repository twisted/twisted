
from twisted.internet import reactor, threads, interfaces, abstract
from twisted.python import threadable

import zope.interface as zi

try:
    import pyipc
except ImportError:
    print ("you must have pyipc installed "
           "(http://www.theory.org/~mac4/software/) to use this transport")
    # XXX: what to do here?
    raise

threadable.init()

class IPCConnector(abstract.FileDescriptor):
    def connectionLost(self, reason):
        raise NotImplementedError

    def writeSomeData(self, data):
        raise NotImplementedError

    def doWrite(self):
        raise NotImplementedError

    def write(self, data):
        raise NotImplementedError

    def writeSequence(self, iovec):
        raise NotImplementedError

    def loseConnection(self):
        raise NotImplementedError

    def startWriting(self):
        raise NotImplementedError

    def startReading(self):
        raise NotImplementedError

    def stopReading(self):
        raise NotImplementedError

    def stopWriting(self):
        raise NotImplementedError

    def registerProducer(self, producer, streaming):
        raise NotImplementedError

    def unregisterProducer(self):
        raise NotImplementedError

    def stopConsuming(self):
        raise NotImplementedError

    def resumeProducing(self):
        raise NotImplementedError

    def pauseProducing(self):
        raise NotImplementedError

    def stopProducing(self):
        raise NotImplementedError

    def fileno(self):
        raise NotImplementedError


class IPCMessageQueueTransport(object):
    zi.implements(interfaces.ITransport)

    def write(self, data):
        raise NotImplementedError

    def writeSequence(self, data):
        raise NotImplementedError

    def loseConnection(self):
        raise NotImplementedError

    def getPeer(self):
        raise NotImplementedError

    def getHost(self):
        raise NotImplementedError

    
