from twisted.internet import event, passport, main
from twisted.spread import pb

application = main.Application("event")
i = passport.Identity("guest", application)
i.setPassword("guest")
application.authorizer.addIdentity(i)
bf = pb.BrokerFactory(application)
svc = event.EventPublishService("event", application)
i.addKeyForPerspective(svc.getPerspectiveNamed('any'))
application.listenOn(pb.portno, bf)
