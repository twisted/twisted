# Twisted, the Framework of Your Internet
# Copyright (C) 2002 Bryce "Zooko" Wilcox-O'Hearn
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

"""Zooko's implementation of Gnutella."""

from twisted.protocols.gnutella import GnutellaTalker

from twisted.python import usage        # twisted command-line processing

from twisted.zoot.AFactory import AFactory
from twisted.zoot.zoot import Zoot

class Options(usage.Options):
    optParameters = [["port", "p", 3653, "Port number to listen on for Gnutella protocol."],]

def updateApplication(app, config):
    theBigZoot = Zoot(app)
    f = AFactory(GnutellaTalker, theBigZoot)
    app.listenTCP(int(config["port"]), f)
