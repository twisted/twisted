# -*- Python -*-

"""Example of rate-limiting your web server.

Caveat emptor: While the transfer rates imposed by this mechanism will
look accurate with wget's rate-meter, don't forget to examine your network
interface's traffic statistics as well.  The current implementation tends
to create lots of small packets in some conditions, and each packet carries
with it some bytes of overhead.  Check to make sure this overhead is not
costing you more bandwidth than you are saving by limiting the rate!
"""

from twisted.protocols import htb
# for picklability
import shaper

serverFilter = htb.HierarchicalBucketFilter()
serverBucket = htb.Bucket()

# Cap total server traffic at 20 kB/s
serverBucket.maxburst = 20000
serverBucket.rate = 20000

serverFilter.buckets[None] = serverBucket

# Web service is also limited per-host:
class WebClientBucket(htb.Bucket):
    # Your first 10k is free
    maxburst = 10000
    # One kB/s thereafter.
    rate = 1000

webFilter = htb.FilterByHost(serverFilter)
webFilter.bucketFactory = shaper.WebClientBucket

servertype = "web" # "chargen"

if servertype == "web":
    from twisted.web import server, static
    site = server.Site(static.File("/var/www"))
    site.protocol = htb.ShapedProtocolFactory(site.protocol, webFilter)
elif servertype == "chargen":
    from twisted.protocols import wire
    from twisted.internet import protocol

    site = protocol.ServerFactory()
    site.protocol = htb.ShapedProtocolFactory(wire.Chargen, webFilter)
    #site.protocol = wire.Chargen

from twisted.internet import reactor
reactor.listenTCP(8000, site)
reactor.run()
