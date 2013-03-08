from twisted.internet import protocol, reactor, defer, utils
import pwd
import os


# Yet another back-end

class LocalFingerService(service.Service):

    implements(IFingerService)

    def getUser(self, user):
        user = user.strip()
        try:
            entry = pwd.getpwnam(user)
        except KeyError:
            return defer.succeed("No such user")
        try:
            f = file(os.path.join(entry[5],'.plan'))
        except (IOError, OSError):
            return defer.succeed("No such user")
        data = f.read()
        data = data.strip()
        f.close()
        return defer.succeed(data)
    
    def getUsers(self):
        return defer.succeed([])



f = LocalFingerService()
