"""
I am a support module for creating reality servers with mktap.
"""

usage_message = """Usage:

  mktap reality -m *map.rpl*

Reality PickLe files are created using the 'gnusto' utility on a build_map file
from a Twisted Reality distribution.  Some realities can be found at
http://twistedmatrix.com/reality.epy."""

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
    optStrings = [["map", "m", None]]


def getPorts(app, config):
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
    bf = pb.BrokerFactory(app)

    return [(8080, site),
            (4040, spigot),
            (8787, bf)]
