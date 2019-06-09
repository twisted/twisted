
class IFingerSetterService(Interface):

    def setUser(user, status):
        """Set the user's status to something"""

# Advantages of latest version

@implementer(IFingerService, IFingerSetterService)
class MemoryFingerService(service.Service):
    def __init__(self, users):
        self.users = users

    def getUser(self, user):
        return defer.succeed(self.users.get(user, b"No such user"))

    def getUsers(self):
        return defer.succeed(list(self.users.keys()))

    def setUser(self, user, status):
        self.users[user] = status


f = MemoryFingerService({b'moshez': b'Happy and well'})
serviceCollection = service.IServiceCollection(application)
strports.service("tcp:1079:interface=127.0.0.1", IFingerSetterFactory(f)
                   ).setServiceParent(serviceCollection)
