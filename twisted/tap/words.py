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
from twisted.words import service, ircservice
import sys

class Options(usage.Options):
    optStrings = [["irc", "i", "6667"],
                  ["port", "p", str(pb.portno)]]

def getPorts(app, config):
    s = service.Service()
    b = pb.BrokerFactory()
    b.addService("words", s)
    t = ircservice.IRCGateway(s)
    portno = int(config.port)
    ircport = int(config.irc)
    return [(int(portno), b),
            (int(ircport), t)]
