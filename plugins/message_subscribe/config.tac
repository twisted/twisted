from twisted.internet import passport, main
from twisted.spread import pb
from message_subscribe import event

application = main.Application("event")
i = passport.Identity("guest", application)
i.setPassword("guest")
application.authorizer.addIdentity(i)
bf = pb.BrokerFactory(application)
svc = event.EventPublishService("event", application)
i.addKeyForPerspective(svc.getPerspectiveNamed('any'))
application.listenTCP(pb.portno, bf)
