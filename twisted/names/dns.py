
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

from twisted.protocols import dns, protocol
from twisted.internet import tcp, udp, main
import random, string, struct

DNS, TCP = range(2)

class DNSBoss:
    protocols = (dns.DNS, dns.DNSOnTCP)
    portPackages = (udp, tcp)

    def __init__(self):
        self.pending = {}
        self.next = 0
        self.factories = [None, None]
        self.ports = [None, None]

    def createFactory(self, i):
        if self.factories[i] is None:
            self.factories[i] = protocol.Factory()
            self.factories[i].protocol = self.protocols[ i ]
            self.factories[i].boss = self

    def createUDPFactory(self):
        self.createFactory(0)

    def createTCPFactory(self):
        self.createFactory(1)

    def createBothFactories(self):
        self.createFactory(0)
        self.createFactory(1)

    def startListening(self, i, portNum=0):
        self.createFactory(i)
        if self.ports[i] is None:
            self.ports[i] = self.portPackages[i].Port(portNum, 
                                                      self.factories[i])
            self.ports[i].startListening()

    def startListeningUDP(self, portNum=0):
        self.startListening(0, portNum)

    def startListeningTCP(self, portNum=0):
        self.startListening(1, portNum)

    def startListeningBoth(self, portNum = 0):
        self.startListening(0, portNum)
        self.startListening(1, portNum)

    def queryUDP(self, addr, name, callback, type=1, cls=1, recursive=1):
        self.startListeningUDP()
        transport = self.ports[0].createConnection(addr)
        return transport.protocol.query(name, callback, type, cls, recursive)

    def queryTCP(self, addr, name, callback, type=1, cls=1, recursive=1):
        self.createTCPFactory()
        protocol = self.factories[1].buildProtocol(addr)
        protocol.setQuery(name, callback, type, cls)
        transport = tcp.Client(addr[0], addr[1], protocol, recursive)

    def stopReading(self, i):
        if self.ports[i] is not None:
            self.ports[i].stopReading()
        self.ports[i], self.factories[i] = None, None

    def stopReadingUDP(self):
        self.stopReading(0)

    def stopReadingTCP(self):
        self.stopReading(1)

    def stopReadingBoth(self):
        self.stopReading(0)
        self.stopReading(1)

    def addPending(self, callback):
        self.next = self.next + 1
        self.pending[self.next] = callback
        return self.next

    def removePending(self, id):
        try:
            del self.pending[id]
        except KeyError:
            pass

    def accomplish(self, key, data):
        callback = self.pending.get(key)
        if callback is not None:
            del self.pending[key]
            callback(data)


class SentQuery:

    def __init__(self, name, type, callback, errback, boss, nameservers):
        self.callback = callback
        self.errback = errback
        self.ids = []
        self.done = 0
        self.boss = boss
        for nameserver in nameservers:
            self.ids.append(boss.queryUDP((nameserver, 53), name, 
                                          self.getAnswer, type=type))

    def getAnswer(self, message):
        self.done = 1
        self.removeAll()
        if not message.answers:
            self.errback()
            return
        process = getattr(self, 'processAnswer_%d' % message.answers[0].type, 
                          None)
        if process is None:
            self.errback()
            return
        self.callback(process(message))

    def processAnswer_1(self, message):
        answer = random.choice(message.answers)
        return string.join(map(str, map(ord, answer.data)), '.')

    def processAnswer_15(self, message):
        answers = []
        for answer in message.answers:
            priority = struct.unpack("!H", answer.data[:2])
            answer.strio.seek(answer.strioOff+2)
            n = dns.Name()
            n.decode(answer.strio)
            answers.append((priority, n.name))
        answers.sort()
        return answers

    def timeOut(self):
        if not self.done:
            self.removeAll()
            self.errback()
        self.done = 1

    def removeAll(self):
        for id in self.ids:
            self.boss.removePending(id)
        self.ids = []


class Resolver:

    def __init__(self, nameservers, boss=None):
        self.nameservers = nameservers
        self.boss = boss or DNSBoss()
        self.next = 0

    def resolve(self, name, callback, errback=None, type=1, timeout=10):
        query = SentQuery(name, type, callback, errback, self.boss, 
                          self.nameservers)
        main.theTimeouts.later(query.timeOut, timeout)
