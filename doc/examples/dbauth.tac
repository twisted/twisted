#!python

from twisted.internet.app import Application
from twisted.internet import passport
from twisted.words import service, ircservice
from twisted.enterprise import adbapi, dbpassport, dbgadgets
from twisted.web import server

auth = dbpassport.DatabaseAuthorizer(adbapi.ConnectionPool("pyPgSQL.PgSQL", "localhost:5432", database="sean"))
a = Application("db-auth", authorizer=auth)
ws = service.Service("twisted.words", a)

gdgt = dbgadgets.IdentitiesGadget(auth)

a.listenOn(8486, server.Site(gdgt))

a.listenTCP(6667, ircservice.IRCGateway(ws))

application = a
