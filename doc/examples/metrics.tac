#!python
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

from twisted.internet import main, passport
from twisted.spread import pb
from twisted.enterprise import adbapi
from twisted.web import widgets, server

from twisted.metrics import metricserv
from twisted.metrics import gadgets

# Create Twisted application object
application = main.Application("metrics-manager")

# Connect to a database.
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="twisted")

# Create the service
metricsService = metricserv.MetricsManagerService("metrics", application, dbpool)

# Create a user
ident = passport.Identity("test", application)
ident.setPassword("sss")
client = metricsService.createPerspective("test")
ident.addKeyForPerspective(client)
application.authorizer.addIdentity(ident)

# Create Metrics object
gdgt = gadgets.MetricsGadget(application, metricsService)

# Accept incoming connections!
application.listenOn(8485, server.Site(gdgt))

r = pb.AuthRoot(application)
application.listenOn(pb.portno, pb.BrokerFactory(r))

# Done.
