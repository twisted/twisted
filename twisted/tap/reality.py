
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
I am a support module for creating reality servers with mktap.
"""

# System Imports
from cPickle import load
import sys

# Twisted Imports
from twisted.reality import plumbing, reality
from twisted.internet import tcp, main
from twisted.web import server
from twisted.python import usage
from twisted.spread import pb

class Options(usage.Options):
    synopsis="Usage: mktap reality -m *map.rpl*"
    optStrings = [["map", "m", None]]

    longdesc = """Reality PickLe files are created using the 'gnusto'
utility on a build_map file from a Twisted Reality distribution.  Some
realities can be found at http://twistedmatrix.com/reality.epy.
"""

def updateApplication(app, config):
    if not config.map:
        raise Exception("Please give a map name")
    print 'Loading %s...' % config.map
    sys.stdout.flush()
    rdf = reality._default = load(open(config.map,'rb'))
    rdf.setApplication(app)
    # Should this be considered 'Legacy'?
    rdf.addPlayersAsIdentities()
    print 'Loaded.'
    app.addDelayed(rdf)

    spigot = plumbing.Spigot(rdf)
    site = server.Site(plumbing.Web(rdf))
    bf = pb.BrokerFactory(pb.AuthRoot(app))

    app.listenTCP(8080, site)
    app.listenTCP(4040, spigot)
    app.listenTCP(8787, bf)
