# -*- Python -*-
from twisted.internet import app
from twisted.issues import robot
from twisted.web import server, static, script, trp
from twisted.spread import pb
from twisted.manhole import service
from twisted import words
import twisted.words.service
import twisted.words.ircservice
import twisted.words.botbot
from twisted.cred.authorizer import DefaultAuthorizer

application = app.Application("issueconduit")
authorizer = DefaultAuthorizer(application)

word = words.service.Service("twisted.words", application, authorizer)
word.addBot("IssueBot", robot.createBot())
word.addBot("BotBot", words.botbot.createBot())
testuser = word.createParticipant("test")
i = testuser.makeIdentity("test")

root = static.File(".")
root.processors = { '.rpy': script.ResourceScript,
                    '.trp': trp.ResourceUnpickler }
web = server.Site(root)

bkr = pb.BrokerFactory(pb.AuthRoot(authorizer))
application.listenTCP(8787, bkr)
application.listenTCP(8080, web)
application.listenTCP(6667, words.ircservice.IRCGateway(word))
