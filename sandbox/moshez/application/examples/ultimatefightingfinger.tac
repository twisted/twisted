from twisted.application import service, internet
from twisted.web import resource, server
from twisted.spread import pb
import finger

m = finger.makeService('users')
f = m.getServiceNamed('finger')
site = server.Site(resource.IResource(f))
i = internet.TCPServer(79, finger.IFingerFactory(f))
i.setServiceParent(m)
i.privileged = 1
i = internet.TCPServer(80, site)
i.setServiceParent(m)
i.privileged = 1
i = finger.IIRCClientFactory(f)
i.nickname = 'fingerbot'
internet.TCPClient('irc.freenode.org', 6667, i).setServiceParent(m)
s = internet.TCPServer(8889, pb.BrokerFactory(finger.IPerspectiveFinger(f)))
s.setServiceParent(m)
application = service.Application('finger', 1, 1)
m.setServiceParent(service.IServiceCollection(application))
