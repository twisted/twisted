

from twisted.python import defer
from twisted.python.failure import Failure

class LocalMethod:
    def __init__(self, local, name):
        self.local = local
        self.name = name

    def __call__(self, *args, **kw):
        apply(self.local.callRemote, (self.key,)+args, kw)

class LocalAsRemote:
    """
    A class useful for emulating the effects of remote behavior locally.
    """
    def callRemote(self, name, *args, **kw):
        """Call a specially-designated local method.

        self.callRemote('x') will first try to invoke a method named
        sync_x and return its result (which should probably be a
        Deferred).  Second, it will look for a method called async_x,
        which will be called and then have its result (or Failure)
        automatically wrapped in a Deferred
        """
        if hasattr(self, 'sync_'+name):
            return apply(getattr(self, 'sync_'+name), args, kw)
        try:
            return defer.succeed(apply(getattr(self, "async_" + name),
                                       args, kw))
        except:
            return defer.failure(Failure())

    def remoteMethod(self, name):
        return Method(self, name)
