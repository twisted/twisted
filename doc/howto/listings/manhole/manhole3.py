#! /usr/bin/python

from twisted.internet.app import Application
from twisted.internet.protocol import Factory
from twisted.protocols.wire import QOTD

app = Application("demo")

# add QOTD server
f = Factory()
f.protocol = QOTD
app.listenTCP(8123, f)

# add manhole with username and password
from twisted.tap.manhole import Options, updateApplication
o = Options()
o.parseOptions(["--user", "boss", "--password", "sekrit"])
updateApplication(app, o)

app.run()
