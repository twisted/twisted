from twisted.internet import app
from twisted.issues import repo, robot
from twisted.web import server, static, script, trp
from twisted.spread import pb
from twisted.manhole import service
from twisted import words
application = app.Application("issueconduit")

r = repo.IssueRepository("twisted.issues", application)

word = words.service.Service("twisted.words", application)
word.addBot("IssueBot", robot.createBot())
testuser = word.createParticipant("test")
i = testuser.makeIdentity("test")

root = static.File(".")
root.processors = { '.rpy': script.ResourceScript, '.trp': trp.ResourceUnpickler}
web = server.Site(root)

#m = service.Service("twisted.manhole", application)
#m.createPerspective("test").setIdentity(i)
bkr = pb.BrokerFactory(pb.AuthRoot(application))
application.listenTCP(8787, bkr)
application.listenTCP(8080, web)
