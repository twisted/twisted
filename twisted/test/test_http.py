
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
from twisted.protocols import http, protocol
from twisted.test.test_protocols import StringIOWithoutClosing
import string


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


class HTTPLoopbackTestCase(unittest.TestCase):
    
    expectedHeaders = {'Request' : '/foo/bar',
                       'Command' : 'GET',
                       'Version' : '1.0',
                       'Content-Length' : '10'}
    numHeaders = 0
    
    def _handleResponse(self, data):
        self.assertEquals(data, '0123456789')
    
    def _handleHeaders(self, key, value):
        self.numHeaders = self.numHeaders + 1
        self.assertEquals(self.expectedHeaders[key], value)
    
    def _handleEndHeaders(self):
        self.assertEquals(self.numHeaders, 4)
    
    def testLoopback(self):
        pass
        # XXX add test here

    
    