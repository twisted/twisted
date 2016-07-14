from __future__ import print_function

from twisted.internet import reactor


def gotIP(ip):
    print("IP of 'localhost' is", ip)
    reactor.stop()

reactor.resolve('localhost').addCallback(gotIP)
reactor.run()
