# -*- coding: Latin-1 -*-

import struct

from twisted.trial import unittest
from twisted.protocols import http
from twisted.web import server
from twisted.web import resource

from predicates import Tautology, Contradiction
from predicates import Address

class Transport:
    def __init__(self, peer = ('127.0.0.1', 12345)):
        self.peer = peer
    
    def getPeer(self):
        return ('TCP',) + self.peer

class AddressTestCase(unittest.TestCase):
    def setUp(self):
        self.proto = http.HTTPChannel()
        self.proto.transport = Transport()
        self.request = server.Request(self.proto, 0)
        self.request.client = ('TCP', '127.0.0.1', 12345)
        self.resource = resource.Resource()

    def testEqual(self):
        a = (Address == '127.0.0.1/255.255.255.255')

        self.failUnless(a.check(self.resource, self.request))
        
        i = 0
        step = (2 ** 25) - 1
        while i < 2 ** 32:
            ip = '%d.%d.%d.%d' % tuple(struct.unpack('BBBB', struct.pack('I', i)))
            if ip != '127.0.0.1':
                self.request.client = ('TCP', ip, 12345)
                self.failIf(a.check(self.resource, self.request))
            i = i + step

    def testSubnetMask(self):
        a = (Address == '127.0.0.1/255.255.0.0')
        
        for i in range(255):
            for j in range(255):
                self.request.client = ('TCP', '127.0.%d.%d' % (i, j), 12345)
                self.failUnless(a.check(self.resource, self.request))
        
        mustFail = [
            '127.1.0.1', '128.0.0.1', '126.0.0.0'
        ]
        for ip in mustFail:
            self.request.client = ('TCP', ip, 12345)
            self.failIf(a.check(self.resource, self.request))

    def testInequal(self):
        a = (Address != '127.0.0.1')

        self.request.client = ('TCP', '127.0.0.1', 9478)
        self.failIf(a.check(self.resource, self.request))
        
        i = 0
        step = (2 ** 25) - 1
        while i < 2 ** 32:
            ip = '%d.%d.%d.%d' % tuple(struct.unpack('BBBB', struct.pack('I', i)))
            if ip != '127.0.0.1':
                self.request.client = ('TCP', ip, 12345)
                self.failUnless(a.check(self.resource, self.request),
                    'Erroneously disallowing ' + ip)
            i = i + step

    def testInequalSubnetMask(self):
        a = (Address == '192.168.1.0/255.255.255.0')
        
        for i in range(255):
            self.request.client = ('TCP', '192.168.1.%d' % (i,), 12345)
            self.failUnless(a.check(self.resource, self.request))
            self.request.client = ('TCP', '192.%d.2.%d' % (i, i), 12345)
            self.failIf(a.check(self.resource, self.request))
