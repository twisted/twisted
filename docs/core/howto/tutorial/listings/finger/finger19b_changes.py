
from twisted.internet import protocol, reactor, defer, utils
import pwd

# Another back-end

@implementer(IFingerService)
class LocalFingerService(service.Service):
    def getUser(self, user):
    # need a local finger daemon running for this to work
        return utils.getProcessOutput("finger", [user])

    def getUsers(self):
        return defer.succeed([])


f = LocalFingerService()
