
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

"""Test HTTP support."""

from pyunit import unittest
from twisted.protocols import http, protocol, loopback
from twisted.test.test_protocols import StringIOWithoutClosing
import string, random


class DateTimeTest(unittest.TestCase):
    """Test date parsing functions."""

    def testRoundtrip(self):
        for i in range(10000):
            time = random.randint(0, 2000000000)
            timestr = http.datetimeToString(time)
            time2 = http.stringToDatetime(timestr)
            self.assertEquals(time, time2)


class OrderedDict:

    def __init__(self, dict):
        self.dict = dict
        self.l = []

    def __setitem__(self, k, v):
        self.l.append(k)
        self.dict[k] = v

    def __getitem__(self, k):
        return self.dict[k]

    def items(self):
        result = []
        for i in self.l:
            result.append((i, self.dict[i]))
        return result

    def __getattr__(self, attr):
        return getattr(self.dict, attr)


class DummyHTTPHandler(http.Request):

    def process(self):
        self.headers = OrderedDict(self.headers)
        self.content.seek(0, 0)
        data = self.content.read()
        length = self.getHeader('content-length')
        request = "'''\n"+str(length)+"\n"+data+"'''\n"
        self.setResponseCode(200)
        self.setHeader("Request", self.uri)
        self.setHeader("Command", self.method)
        self.setHeader("Version", self.clientproto)
        self.setHeader("Content-Length", len(request))
        self.write(request)
        self.finish()


class LoopbackHTTPClient(http.HTTPClient):

    def connectionMade(self):
        self.sendCommand("GET", "/foo/bar")
        self.sendHeader("Content-Length", 10)
        self.endHeaders()
        self.transport.write("0123456789")


class HTTP1_0TestCase(unittest.TestCase):

    requests = '''\
GET / HTTP/1.0

GET / HTTP/1.1
Accept: text/html

'''
    requests = string.replace(requests, '\n', '\r\n')
    
    expected_response = "HTTP/1.0 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.0\015\012Content-length: 13\015\012\015\012'''\012None\012'''\012"

    def testBuffer(self):
        b = StringIOWithoutClosing()
        a = http.HTTPChannel()
        a.requestFactory = DummyHTTPHandler
        a.makeConnection(protocol.FileWrapper(b))
        # one byte at a time, to stress it.
        for byte in self.requests:
            a.dataReceived(byte)
        a.connectionLost()
        value = b.getvalue()
        if value != self.expected_response:
            for i in range(len(value)):
                if len(self.expected_response) <= i:
                    print `value[i-5:i+10]`, `self.expected_response[i-5:i+10]`
                elif value[i] != self.expected_response[i]:
                    print `value[i-5:i+10]`, `self.expected_response[i-5:i+10]`
                    break
            print '---VALUE---'
            print repr(value)
            print '---EXPECTED---'
            print repr(self.expected_response)
            raise AssertionError


class HTTP1_1TestCase(HTTP1_0TestCase):

    requests = '''\
GET / HTTP/1.1
Accept: text/html

POST / HTTP/1.1
Content-Length: 10

0123456789POST / HTTP/1.1
Content-Length: 10

0123456789HEAD / HTTP/1.1

'''
    requests = string.replace(requests, '\n', '\r\n')
    
    expected_response = "HTTP/1.1 200 OK\015\012Request: /\015\012Command: GET\015\012Version: HTTP/1.1\015\012Content-length: 13\015\012\015\012'''\012None\012'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: POST\015\012Version: HTTP/1.1\015\012Content-length: 21\015\012\015\012'''\01210\0120123456789'''\012HTTP/1.1 200 OK\015\012Request: /\015\012Command: HEAD\015\012Version: HTTP/1.1\015\012Content-length: 13\015\012\015\012"


class HTTP0_9TestCase(HTTP1_0TestCase):

    requests = '''\
GET /
'''
    requests = string.replace(requests, '\n', '\r\n')
    
    expected_response = "'''\012None\012'''\012"


class HTTPLoopbackTestCase(unittest.TestCase):
    
    expectedHeaders = {'Request' : '/foo/bar',
                       'Command' : 'GET',
                       'Version' : 'HTTP/1.0',
                       'Content-Length' : '21'}
    numHeaders = 0
    
    def _handleStatus(self, version, status, message):
        self.assertEquals(version, "HTTP/1.0")
        self.assertEquals(status, "200")
    
    def _handleResponse(self, data):
        self.assertEquals(data, "'''\n10\n0123456789'''\n")
    
    def _handleHeader(self, key, value):
        self.numHeaders = self.numHeaders + 1
        self.assertEquals(self.expectedHeaders[key], value)
    
    def _handleEndHeaders(self):
        self.assertEquals(self.numHeaders, 4)
    
    def testLoopback(self):
        server = http.HTTPChannel()
        server.requestFactory = DummyHTTPHandler
        client = LoopbackHTTPClient()
        client.handleResponse = self._handleResponse
        client.handleHeader = self._handleHeader
        client.handleEndHeaders = self._handleEndHeaders
        client.handleStatus = self._handleStatus
        loopback.loopback(server, client)


class PRequest:
    """Dummy request for persistence tests."""

    def __init__(self, **headers):
        self.received_headers = headers
        self.headers = {}

    def getHeader(self, k):
        return self.received_headers.get(k, '')
    def setHeader(self, k, v):
        self.headers[k] = v


class PersistenceTestCase(unittest.TestCase):
    """Tests for persistent HTTP connections."""

    ptests = [#(PRequest(connection="Keep-Alive"), "HTTP/1.0", 1, {'connection' : 'Keep-Alive'}),
              (PRequest(), "HTTP/1.0", 0, {'connection': None}),
              (PRequest(connection="close"), "HTTP/1.1", 0, {'connection' : 'close'}),
              (PRequest(), "HTTP/1.1", 1, {'connection': None}),
              (PRequest(), "HTTP/0.9", 0, {'connection': None}),
              ]
              
              
    def testAlgorithm(self):
        c = http.HTTPChannel()
        for req, version, correctResult, resultHeaders in self.ptests:
            result = c.checkPersistence(req, version)
            self.assertEquals(result, correctResult)
            for header in resultHeaders.keys():
                self.assertEquals(req.headers.get(header, None), resultHeaders[header])


if __name__ == '__main__':
    unittest.main()
