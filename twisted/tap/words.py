
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

from twisted.python import usage
from twisted.spread import pb
from twisted.words import service, ircservice, webwords
from twisted.web import server

import sys

class Options(usage.Options):
    synopsis = "Usage: mktap words [options]"
    optParameters = [["irc", "i", "6667", "Port to run the IRC server on."],
                  ["port", "p", str(pb.portno),
                   "Port to run the Words service on."],
                  ["web", "w", "8080",
                   "Port to run the web interface on."]]

    longdesc = "Makes a twisted.words service and support servers."

def updateApplication(app, config):
    svc = service.Service("twisted.words", app)
    bkr = pb.BrokerFactory(pb.AuthRoot(app))
    irc = ircservice.IRCGateway(svc)
    adm = server.Site(webwords.WordsGadget(svc))

    app.listenTCP(int(config.opts['port']), bkr)
    app.listenTCP(int(config.opts['irc']), irc)
    app.listenTCP(int(config.opts['web']), adm)
