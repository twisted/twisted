# organized-finger.tac
# eg:  twistd -ny organized-finger.tac

import finger

from twisted.spread import pb
from twisted.web import resource, server
from twisted.application import internet, service

application = service.Application('finger', uid=1, gid=1)
f = finger.FingerService('/etc/users')
internet.TCPServer(79, finger.IFingerFactory(f)
                   ).setServiceParent(application)

site = server.Site(resource.IResource(f))
internet.TCPServer(8000, site
                   ).setServiceParent(application)

internet.SSLServer(443, site, finger.ServerContextFactory()
                   ).setServiceParent(application)

i = finger.IIRCClientFactory(f)
i.nickname = 'fingerbot'
internet.TCPClient('irc.freenode.org', 6667, i
                   ).setServiceParent(application)

internet.TCPServer(8889, pb.PBServerFactory(finger.IPerspectiveFinger(f))
                   ).setServiceParent(application)
