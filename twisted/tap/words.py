
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
