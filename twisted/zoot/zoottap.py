import twisted.protocols.gnutella

from twisted.python import usage        # twisted command-line processing

from twisted.zoot.ZootFactory import ZootFactory

class Options(usage.Options):
    optParameters = [["port", "p", 9118, "Port number to listen on for Gnutella protocol."],]

def updateApplication(app, config):
    port = int(config["port"])
    factory = ZootFactory()
    app.listenTCP(port, factory)
