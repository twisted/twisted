#! /usr/bin/python

from twisted.internet.app import Application
from twisted.internet.protocol import Factory
from twisted.protocols.wire import QOTD
import twisted.manhole.telnet

app = Application("demo")

# add QOTD server
f = Factory()
f.protocol = QOTD
app.listenTCP(8123, f)

# Add a manhole shell
f = twisted.manhole.telnet.ShellFactory()
f.username = "boss"
f.password = "sekrit"
f.namespace['foo'] = 12
app.listenTCP(8007, f)

app.run()
