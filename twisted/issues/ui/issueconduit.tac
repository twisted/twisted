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

# Very basic Twisted stuff.
application = app.Application("issueconduit")
authorizer = DefaultAuthorizer(application)

# The words service, and Issue bot (which automatically creates the repository)
word = words.service.Service("twisted.words", application, authorizer)
issuebot = robot.createBot()
word.addBot("IssueBot", issuebot)
word.addBot("BotBot", words.botbot.createBot())

# A web site.
import os
root = static.File(os.path.dirname(__file__))
root.processors = { '.rpy': script.ResourceScript,
                    '.trp': trp.ResourceUnpickler }

# Demo user.
testuser = word.createParticipant("test")
i = testuser.makeIdentity("test")

# A couple of issues.
from twisted.issues import issue
repo = application.getServiceNamed(issuebot.protoServiceName)
complainer = repo.createPerspective("complainer")
admin = repo.createPerspective("admin")
i1 = repo.reportBug(complainer, "Issue Number One")
i2 = repo.reportBug(complainer, "Issue Number Two")
i3 = repo.reportBug(complainer, "Issue Number Three")
t1 = repo.buildTask(admin, "Build a frobnitz")
i2.setState(issue.PendingTaskCompletion(t1))

# Listen on appropriate ports.
application.listenTCP(8787, pb.BrokerFactory(pb.AuthRoot(authorizer)))
application.listenTCP(8080, server.Site(root))
application.listenTCP(6667, words.ircservice.IRCGateway(word))
