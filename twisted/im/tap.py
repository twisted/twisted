
from proxyui import IRCUIFactory
from twisted.python import usage

class Options(usage.Options):
    optParameters = [["ircport", "p", "6667",
                      "Port to start the IRC server on."]]

def updateApplication(app, config):
    factory = IRCUIFactory()
    app.listenTCP(int(config.opts['ircport']), IRCUIFactory())
