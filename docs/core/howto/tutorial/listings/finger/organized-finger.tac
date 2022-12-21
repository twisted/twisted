# organized-finger.tac
# eg:  twistd -ny organized-finger.tac

import finger

from twisted.application import internet, service, strports
from twisted.internet import defer, endpoints, protocol, reactor
from twisted.python import log
from twisted.spread import pb
from twisted.web import resource, server

application = service.Application("finger", uid=1, gid=1)
f = finger.FingerService("/etc/users")
serviceCollection = service.IServiceCollection(application)
strports.service("tcp:79", finger.IFingerFactory(f)).setServiceParent(serviceCollection)

site = server.Site(resource.IResource(f))
strports.service(
    "tcp:8000",
    site,
).setServiceParent(serviceCollection)

strports.service(
    "ssl:port=443:certKey=cert.pem:privateKey=key.pem", site
).setServiceParent(serviceCollection)

i = finger.IIRCClientFactory(f)
i.nickname = "fingerbot"
internet.ClientService(
    endpoints.clientFromString(reactor, "tcp:irc.freenode.org:6667"), i
).setServiceParent(serviceCollection)

strports.service(
    "tcp:8889", pb.PBServerFactory(finger.IPerspectiveFinger(f))
).setServiceParent(serviceCollection)
