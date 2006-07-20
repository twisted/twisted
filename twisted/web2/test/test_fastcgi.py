
from twisted.trial import unittest
from twisted.web2.channel import fastcgi
from twisted.python import util

class FCGI(unittest.TestCase):
    def testPacketReceived(self):
        '''
        Test that a packet can be received, and that it will cause
        'writePacket' to be called.
        '''
        record = fastcgi.Record(fastcgi.FCGI_GET_VALUES, 0, '')
        req = fastcgi.FastCGIChannelRequest()
        called = []
        def writePacket(rec):
            self.assertEquals(rec.__class__, fastcgi.Record)
            called.append(rec)
        req.writePacket = writePacket
        req.packetReceived(record)
        self.assertEquals(len(called), 1)

    def testPacketWrongVersion(self):
        '''
        Test that a version other than version 1 will raise FastCGIError
        '''
        record = fastcgi.Record(fastcgi.FCGI_GET_VALUES, 0, '', version=2)
        req = fastcgi.FastCGIChannelRequest()
        self.failUnless(util.raises(fastcgi.FastCGIError, req.packetReceived, record))

    def testPacketBadType(self):
        '''
        Test that an invalid packet type will raise FastCGIError
        '''
        record = fastcgi.Record(99999, 0, '')
        req = fastcgi.FastCGIChannelRequest()
        self.failUnless(util.raises(fastcgi.FastCGIError, req.packetReceived, record))

    def testParseLongName(self):
        '''
        Test the code paths for parsing a name or value with >= 128 bytes. The
        length prefixing is done differently in this case.
        '''
        self.assertEqual(
                [('x'*128, 'y')],
                list(fastcgi.parseNameValues(fastcgi.writeNameValue('x'*128, 'y'))))

    def testParseLongValue(self):
        '''
        Test parsing a long value.
        '''
        self.assertEqual(
                [('x', 'y'*128)],
                list(fastcgi.parseNameValues(fastcgi.writeNameValue('x', 'y'*128))))

