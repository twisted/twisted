# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This shows an example of a bare-bones distributed web set up.  The "master" and
"slave" parts will usually be in different files -- they are here together only
for brevity of illustration.  In normal usage they would each run in a separate
process.

Usage:
    $ python silly-web.py

Then visit http://localhost:19988/.
"""

from twisted.internet import reactor
from twisted.spread import pb
from twisted.web import distrib, server, static

# The "master" server
site = server.Site(distrib.ResourceSubscription("unix", ".rp"))
reactor.listenTCP(19988, site)

# The "slave" server
fact = pb.PBServerFactory(distrib.ResourcePublisher(server.Site(static.File("static"))))

reactor.listenUNIX("./.rp", fact)
reactor.run()
