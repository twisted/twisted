#!python

from twisted.internet.app import Application
from twisted.internet import passport
from twisted.words import service, ircservice
from twisted.enterprise import adbapi, dbpassport
auth = dbpassport.DatabaseAuthorizer(adbapi.ConnectionPool("pyPgSQL.PgSQL", database="twisted"))
a = Application("db-auth", authorizer=auth)
ws = service.Service("twisted.words", a)
p = ws.createParticipant("glyph")
p.makeIdentity("test-password")
a.listenTCP(6667, ircservice.IRCGateway(ws))

application = a
