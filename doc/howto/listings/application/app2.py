#! /usr/bin/python

from twisted.internet.app import Application
from twisted.protocols.wire import Daytime
from twisted.internet.protocol import Factory

application = Application("daytimer")
f = Factory()
f.protocol = Daytime
application.listenTCP(8813, f)

application.save("start")
