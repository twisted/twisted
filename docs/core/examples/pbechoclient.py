
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.internet import reactor
from twisted.spread import pb
from twisted.cred.credentials import UsernamePassword

from pbecho import DefinedError

def success(message):
    print("Message received:",message)
    # reactor.stop()

def failure(error):
    t = error.trap(DefinedError)
    print("error received:", t)
    reactor.stop()

def connected(perspective):
    perspective.callRemote('echo', "hello world").addCallbacks(success, failure)
    perspective.callRemote('error').addCallbacks(success, failure)
    print("connected.")


factory = pb.PBClientFactory()
reactor.connectTCP("localhost", pb.portno, factory)
factory.login(
    UsernamePassword("guest", "guest")).addCallbacks(connected, failure)

reactor.run()
