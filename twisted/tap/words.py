"""
I am a support module for creating chat servers with mktap.
"""

usage_message = """Usage:

  mktap words [--irc *irc-port*]
              [--port *pb-port*]

Run this to generate a TAP for a twisted.words server."""

from twisted.internet import tcp
from twisted.python import usage
from twisted.spread import pb
from twisted.words import service, ircservice, webwords

import sys

usage_message = """Usage:
  mktap words [--irc portno] [--port portno] [--web portno]
"""

class Options(usage.Options):
    optStrings = [["irc", "i", "6667"],
                  ["port", "p", str(pb.portno)],
                  ["web", "w", "8080"]]

def getPorts(app, config):
    svc = service.Service("twisted.words", app)
    bkr = pb.BrokerFactory(app)
    irc = ircservice.IRCGateway(svc)
    adm = webwords.WebWordsAdminSite(svc)
    return [(int(config.port), bkr),
            (int(config.irc), irc),
            (int(config.web), adm)]
