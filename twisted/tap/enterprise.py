
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

from twisted.enterprise import dbserver, dbservice
from twisted.spread import pb
from twisted.internet import passport
from twisted.python import usage

usage_message = """Usage:

  mktap enterprise [options]

Options:

        -s, --service
                database vendor service to load (example: postgres,
                sybase, oracle)
        -r, --server
                database server instance to connect to (example:
                mySybaseServer)
        -d, --database
                database instance to connect to (example: twisted, template1,
                masterdb).  Default is "twisted", which the included scripts
                will create.
        -u, --username
                username to connect to the database
        -p, --password
                password to connect to the database
        -c, --connections
                number of connections (threads) to spawn
            --pbusername
                username to allow connections to this service with
            --pbpassword
                password to allow connections to this service with
            --pbport
                port to start pb service on

This creates a DBService instance, which is a Perspective Broker service that allows access to a database.

"""


class Options(usage.Options):
    optStrings = [["service","s","postgres"],
                  ["server","r", "default"],
                  ["database","d","twisted"],
                  ["username","u","twisted"],
                  ["password","p","matrix"],
                  ["connections","c","2"],
                  ["pbusername","","twisted"],
                  ["pbpassword","","matrix"],
                  ["pbport", "", str(pb.portno)]]


def getPorts(app, config):
    bf = pb.BrokerFactory(app)
    mgr = dbserver.DbManager(
        service  = config.service,
        server   = config.server,
        database = config.database,
        username = config.username,
        password = config.password,
        numConnections = int(config.connections)
        )
    svc = dbservice.DbService(mgr, app)
    
    i = passport.Identity(config.pbusername, app)
    i.setPassword(config.pbpassword)
    app.authorizer.addIdentity(i)
    p = dbservice.DbUser(config.pbusername, svc, i.name)
    svc.addPerspective(p)
    i.addKeyFor(p)

    return [(int(config.pbport), bf)]


