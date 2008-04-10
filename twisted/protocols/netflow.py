import struct

from twisted.internet import protocol
from twisted.protocols import basic


class NetFlowData(object):
    """

    """
    format = ''
    size = 0
    offset = 0


    def __init__(self, data):
        segment = data[self.offset:self.offset + self.size]
        self.data = struct.unpack(self.format, segment)



class NetFlowHeader(NetFlowData):
    """

    """
    format = '!2H4I2BH'
    size = struct.calcsize(format)
    offset = 0


    def __init__(self, data):
        super(NetFlowHeader, self).__init__(data)
        self.version = self.data[0]
        self.flowCount = self.data[1]
        self.sysUptime = self.data[2]
        self.seconds = self.data[3]
        self.nanoSeconds = self.data[4]
        self.flowsSeen = self.data[5]
        self.engineType = self.data[6]
        self.engineID = self.data[7]
        self.samplingID = self.data[8]
        del(self.data)


class NetFlowRecord(NetFlowData):
    """

    """
    format = '!3I2H4I2H4B2H2BH'
    size = struct.calcsize(format)
    offset = NetFlowHeader.size


    def __init__(self, data):
        super(NetFlowRecord, self).__init__(data)
        self.sourceIP = self.data[0]
        del(self.data)



totalSize = NetFlowHeader.size + NetFlowRecord.size


class NetFlowParser(basic.LineReceiver):
    """

    """



class NetFlowDatagramProtocol(protocol.DatagramProtocol):
    """

    """
    def __init__(self):
        self.records = []
        self._buffer = ''
        self._data = ''


    def stopProtocol(self):
        """
        """
        self.transport = None


    def startProtocol(self):
        """
        """


    def startListening(self):
        """
        """
        from twisted.internet import reactor
        reactor.listenUDP(0, self, maxPacketSize=512)

    def addRecord(self, record):
        self.records.append(record)


    def datagramReceived(self, data, addr):
        self._buffer += data
        div, mod = divmod(len(self._buffer), totalSize)
        if mod == 0 and div != 0:
            for i in xrange(div):
                self.processData(addr)

    def processData(self, addr):
        data, self._buffer = self._buffer[:totalSize], self._buffer[totalSize:]
        header = NetFlowHeader(data)
        record = NetFlowRecord(data)
        print 'Header Data (%s:%s): %s' % (addr[0], addr[1],
            str(header.__dict__))
        print 'Record Data (%s:%s): %s' % (addr[0], addr[1],
            str(record.__dict__))
        print 'Buffer Size: %s' % len(self._buffer)
        print 'Modulus: %s (remainder=%s)' % divmod(len(self._buffer),
            totalSize)
        print '\n'

"""
Flows don't seem to be correct... need to check with the following:

oubiwann@gondor:~$ flow-gen -V5 | flow-send 0/localhost/2055
oubiwann@gondor:~$ flow-gen -V5 | flow-send 0/lorien/2055

flow-gen -V5 -n 100| flow-send 0/localhost/2055
flow-gen -V5 -n 100| flow-send 0/lorien/2055

flow-receive 0/0/2055 | flow-print
flow-receive 0/0/2055 | flow-print -p -w -f 5


Collector code:

from twisted.protocols import netflow
from twisted.application import service, internet

application = service.Application('Test Collector')
nf = netflow.NetFlowDatagramProtocol()
server = internet.UDPServer(2055, nf)
server.setServiceParent(application)

"""
