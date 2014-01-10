from twisted.spread import pb

class LocalForwarder(flavors.Referenceable):
    def remote_foo(self):
        return str(self.local.baz())

class RemoteForwarder(flavors.Referenceable):
    def remote_foo(self):
        return self.remote.callRemote("baz").addCallback(str)
