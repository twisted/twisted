from twisted.internet import app, protocol
from twisted.protocols import wire

f = protocol.Factory()
f.protocol = wire.Echo 

application = app.Application("echo")

application.listenTCP(18899, f)
