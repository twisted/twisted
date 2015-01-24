from TwistedQuotes import quoteproto    # Protocol and Factory
from TwistedQuotes import quoters       # "give me a quote" code
from TwistedQuotes import pbquote       # perspective broker binding
        
from twisted.application import service, internet
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

def makeService(config):
    svc = service.MultiService()
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
        pbfact = pb.PBServerFactory(pbquote.QuoteReader(quoter))
        svc.addService(internet.TCPServer(int(pbport), pbfact))
    svc.addService(internet.TCPServer(port, factory))
    return svc
