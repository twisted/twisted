import quoteproto                       # Protocol and Factory
import quoters                          # "give me a quote" code
import pbquote                          # perspective broker binding
from twisted.python import usage        # twisted command-line processing
from twisted.spread import pb           # Perspective Broker

class Options(usage.Options):
    optParameters = [["port", "p", 8007,
                      "Port number to listen on for QOTD protocol."],
                     ["static", "s", "An apple a day keeps the doctor away.",
                      "A static quote to display."],
                     ["file", "f", None,
                      "A fortune-format text file to read quotes from."],
                     ["pb", "b", None,
                      "Port to listen with PB server"]]

def updateApplication(app, config):
    if config["file"]:                  # If I was given a "file" option...
        # Read quotes from a file, selecting a random one each time,
        quoter = quoters.FortuneQuoter([config['file']])
    else:                               # otherwise,
        # read a single quote from the command line (or use the default).
        quoter = quoters.StaticQuoter(config['static'])
    port = int(config["port"])          # TCP port to listen on
    factory = quoteproto.QOTDFactory(quoter) # here we create a QOTDFactory
    # Finally, set up our factory, with its custom quoter, to create QOTD
    # protocol instances when events arrive on the specified port.
    pbport = config['pb']               # TCP PB port to listen on
    if pbport:
        pbserv = pbquote.QuoteService(quoter, "twisted.quotes", app)
        # create a quotereader "guest" give that perspective a password and
        # create an account based on it, with the password "guest".
        pbserv.createPerspective("guest").makeIdentity("guest")
        pbfact = pb.BrokerFactory(pb.AuthRoot(app))
        app.listenTCP(int(pbport), pbfact)
    app.listenTCP(port, factory)
