#! /usr/bin/python

import twisted.internet.app
from twisted.protocols.wire import Daytime
from twisted.internet.protocol import Factory

app = twisted.internet.app.Application("daytimer")
f = Factory()
f.protocol = Daytime
app.listenTCP(8813, f)

app.save("start")
