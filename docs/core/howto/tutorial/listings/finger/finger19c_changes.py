from twisted.internet import protocol, reactor, defer, utils
import pwd
import os


# Yet another back-end

@implementer(IFingerService)
class LocalFingerService(service.Service):
    def getUser(self, user):
        user = user.strip()
        try:
            entry = pwd.getpwnam(user)
        except KeyError:
            return defer.succeed("No such user")
        try:
            f = open(os.path.join(entry[5],'.plan'))
        except (IOError, OSError):
            return defer.succeed("No such user")
        with f:
            data = f.read()
        data = data.strip()
        return defer.succeed(data)
    
    def getUsers(self):
        return defer.succeed([])



f = LocalFingerService()
