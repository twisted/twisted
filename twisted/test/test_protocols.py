
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

"""
Test cases for twisted.protocols package.
"""

from pyunit import unittest
from twisted.protocols import protocol, basic, http, smtp, pop3 # , netexprs
import string
import StringIO

class StringIOWithoutClosing(StringIO.StringIO):

    def close(self):
        pass

class LineTester(basic.LineReceiver):

    delimiter = '\n'

    def connectionMade(self):
        self.received = []

    def lineReceived(self, line):
        self.received.append(line)
        if line == '':
            self.setRawMode()
        if line[:4] == 'len ':
            self.length = int(line[4:])

    def rawDataReceived(self, data):
        data, rest = data[:self.length], data[self.length:]
        self.length = self.length - len(data)
        self.received[-1] = self.received[-1] + data
        if self.length == 0:
            self.setLineMode(rest)


class LineReceiverTestCase(unittest.TestCase):

    buffer = '''\
len 10

0123456789len 5

1234
len 20
foo 123

0123456789
012345678len 0
foo 5

len 1

a'''

    output = ['len 10', '0123456789', 'len 5', '1234\n',
              'len 20', 'foo 123', '0123456789\n012345678',
              'len 0', 'foo 5', '', 'len 1', 'a']

    def testBuffer(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = LineTester()
            a.makeConnection(protocol.FileWrapper(t))
            for i in range(len(self.buffer)/packet_size + 1):
                s = self.buffer[i*packet_size:(i+1)*packet_size]
                a.dataReceived(s)
            self.failUnlessEqual(self.output, a.received)

class TestNetstring(basic.NetstringReceiver):

    def connectionMade(self):
        self.received = []

    def stringReceived(self, s):
        self.received.append(s)

class TestSafeNetstring(basic.SafeNetstringReceiver):

    MAX_LENGTH = 50
    closed = 0

    def stringReceived(self, s):
        pass

    def connectionLost(self):
        self.closed = 1


class NetstringReceiverTestCase(unittest.TestCase):

    strings = ['hello', 'world', 'how', 'are', 'you123', ':today', "a"*515]

    illegal_strings = ['9999999999999999999999', 'abc', '4:abcde',
                       '51:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab,',]

    def testBuffer(self):
        for packet_size in range(1, 10):
            t = StringIOWithoutClosing()
            a = TestNetstring()
            a.makeConnection(protocol.FileWrapper(t))
            for s in self.strings:
                a.sendString(s)
            out = t.getvalue()
            for i in range(len(out)/packet_size + 1):
                s = out[i*packet_size:(i+1)*packet_size]
                if s:
                    a.dataReceived(s)
            if a.received != self.strings:
                raise AssertionError(a.received)

    def getSafeNS(self):
        t = StringIOWithoutClosing()
        a = TestSafeNetstring()
        a.makeConnection(protocol.FileWrapper(t))
        return a

    def testSafe(self):
        for s in self.illegal_strings:
            r = self.getSafeNS()
            r.dataReceived(s)
            if not r.brokenPeer:
                raise AssertionError("connection wasn't closed on illegal netstring %s" % repr(s))


class DummyHTTPHandler(http.HTTP):

    def requestReceived(self, command, path, version, data):
        request = "'''\n"+str(self.getHeader('content-length'))+"\n"+data+"'''\n"
        self.sendStatus(200, "OK")
        self.sendHeader("Request", path)
        self.sendHeader("Command", command)
        self.sendHeader("Version", version)
        self.sendHeader("Content-Length", len(request))
        self.endHeaders()
        self.transport.write(request)


class HTTPTestCase(unittest.TestCase):


    requests = '''\
GET / HTTP/1.0

GET / HTTP/1.1
Accept: text/html

POST / HTTP/1.1
Content-Length: 10

0123456789HEAD /
POST / HTTP/1.1
Content-Length: 10

0123456789\nHEAD /
'''
    requests = string.replace(requests, '\n', '\r\n')
    expected_response = "HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.0\015\012Content-Length: 9\015\012\015\012'''\012\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.1\015\012Content-Length: 27\015\012\015\012'''\012Accept: text/html\012\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-Length: 38\015\012\015\012'''\012Content-Length: 10\012\0120123456789'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/0.9\015\012Content-Length: 9\015\012\015\012'''\012\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-Length: 38\015\012\015\012'''\012Content-Length: 10\012\0120123456789'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/0.9\015\012Content-Length: 9\015\012\015\012'''\012\012'''\012"
    expected_response = "HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.0\015\012Content-Length: 13\015\012\015\012'''\012None\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.1\015\012Content-Length: 13\015\012\015\012'''\012None\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-Length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/0.9\015\012Content-Length: 11\015\012\015\012'''\01210\012'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-Length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.0 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/0.9\015\012Content-Length: 11\015\012\015\012'''\01210\012'''\012"

    def testBuffer(self):
        b = StringIOWithoutClosing()
        a = DummyHTTPHandler()
        a.makeConnection(protocol.FileWrapper(b))
        # one byte at a time, to stress it.
        for byte in self.requests:
            a.dataReceived(byte)
        a.connectionLost()
        value = b.getvalue()
        if value != self.expected_response:
	    for i in range(len(value)):
                if value[i] != self.expected_response[i]:
                    print `value[i-5:i+10]`, `self.expected_response[i-5:i+10]`
                    break
            print '---VALUE---'
            print repr(value)
            print '---EXPECTED---'
            print repr(self.expected_response)
            raise AssertionError

class DummySMTP(smtp.SMTP):

    def connectionMade(self):
        smtp.SMTP.connectionMade(self)
        self.messages = []

    def handleMessage(self, users, message, success, failure):
        helo, origin = users[0].helo, users[0].orig
        recipients = []
        for user in users:
            recipients.append(user.name+'@'+user.domain)
        self.messages.append((helo, origin, recipients, message))
        success()


class SMTPTestCase(unittest.TestCase):

    messages = [ ('foo.com', 'moshez@foo.com', ['moshez@bar.com'], '''\
From: Moshe
To: Moshe

Hi,
how are you?
'''),
                 ('foo.com', 'tttt@rrr.com', ['uuu@ooo', 'yyy@eee'], '''\
Subject: pass

..rrrr..
''')
              ]

    expected_output = '220 Spammers beware, your ass is on fire\015\012250 Nice to meet you\015\012250 From address accepted\015\012250 Address recognized\015\012354 Continue\015\012250 Delivery in progress\015\012250 From address accepted\015\012250 Address recognized\015\012250 Address recognized\015\012354 Continue\015\012250 Delivery in progress\015\012221 See you later\015\012'

    input = 'HELO foo.com\r\n'
    for _, from_, to_, message in messages:
        input = input + 'MAIL FROM:<%s>\r\n' % from_
        for item in to_:
            input = input + 'RCPT TO:<%s>\r\n' % item
        input = input + 'DATA\r\n'
        for line in string.split(message, '\n')[:-1]:
            if line[:1] == '.': line = '.' + line
            input = input + line + '\r\n'
        input = input + '.' + '\r\n'
    input = input + 'QUIT\r\n'

    def testBuffer(self):
        output = StringIOWithoutClosing()
        a = DummySMTP()
        a.makeConnection(protocol.FileWrapper(output))
        a.dataReceived(self.input)
        if a.messages != self.messages:
            raise AssertionError(a.messages)
        if output.getvalue() != self.expected_output:
            raise AssertionError(`output.getvalue()`)

class DummyPOP3(pop3.POP3):

    magic = '<moshez>'

    def authenticateUserAPOP(self, user, password):
        return DummyMailbox()

class DummyMailbox(pop3.Mailbox):

    messages = [
'''\
From: moshe
To: moshe

How are you, friend?
''']

    def __init__(self):
        self.messages = DummyMailbox.messages[:]

    def listMessages(self):
        return map(len, self.messages)

    def getMessage(self, i):
        return StringIO.StringIO(self.messages[i])

    def getUidl(self, i):
        return str(i)

    def deleteMessage(self, i):
        self.messages[i] = ''

class POP3TestCase(unittest.TestCase):

    def testBuffer(self):
        a = StringIOWithoutClosing()
        dummy = DummyPOP3()
        dummy.makeConnection(protocol.FileWrapper(a))
        lines = string.split('''\
APOP moshez dummy
LIST
UIDL
RETR 1
RETR 2
DELE 1
RETR 1
QUIT''', '\n')
        expected_output = '+OK <moshez>\r\n+OK \r\n+OK 1\r\n1 44\r\n.\r\n+OK \r\n1 0\r\n.\r\n+OK 44\r\nFrom: moshe\r\nTo: moshe\r\n\r\nHow are you, friend?\r\n.\r\n-ERR index out of range\r\n+OK \r\n-ERR message deleted\r\n+OK \r\n'
        for line in lines:
            dummy.lineReceived(line)
        self.failUnlessEqual(expected_output, a.getvalue(),
                             "\nExpected:\n%s\nResults:\n%s\n"
                             % (expected_output, a.getvalue()))

##class ObjectAccumulator(netexprs.PseudoSexprsReceiver):

##    def __init__(self):
##        netexprs.PseudoSexprsReceiver.__init__(self)
##        self.objects = []

##    def objectReceived(self, o):
##        self.objects.append(o)


##class NetexprsReceiverTestCase(unittest.TestCase):

##    object = { (1,2): [1, 'hello', 'world'], 1.0: {}}

##    def testBuffer(self):
##        t = StringIOWithoutClosing()
##        o = ObjectAccumulator()
##        o.makeConnection(protocol.FileWrapper(t))
##        o.sendObject(self.object)
##        output = t.getvalue()
##        o.dataReceived(output)
##        if o.objects[0] != self.object:
##             raise AssertionError(o.objects[0])

testCases = [LineReceiverTestCase, NetstringReceiverTestCase, HTTPTestCase,
             SMTPTestCase, POP3TestCase]
