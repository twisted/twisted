
from twisted.spread import pb
from twisted.python import defer
import copy

True = 1
False = 0

# "Sturdy" references in PB

class PerspectiveConnector:
    def __init__(self, host, port, username, password, serviceName,
                 perspectiveName=None, client=None):
        # perspective-specific stuff
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.serviceName = serviceName
        self.perspectiveName = perspectiveName
        self.client = client
        # remote-reference-type-neutral stuff
        self.reference = None
        self.connecting = False
        self.methodsToCall = []

    def __getstate__(self):
        d = copy.copy(self.__dict__)
        d['reference'] = None
        d['connecting'] = False
        d['methodsToCall'] = []
        return d

    def _cbConnected(self, reference):
        """We've connected.  Reset everything and call all pending methods.
        """
        print 'connected!'
        self.reference = reference
        self.connecting = False
        for method, args, kw, defr in self.methodsToCall:
            apply(reference.callRemote, (method,)+args, kw).addCallbacks(
                defr.callback,
                defr.errback)
            defr.arm()

    def _ebConnected(self, error):
        """We haven't connected yet.  Try again.
        """
        print 'error in connecting', error
        self.startConnecting()

    def startConnecting(self):
        print 'trying to connect...'
        return pb.connect(self.host, self.port, self.username, self.password,
                          self.serviceName, self.perspectiveName, self.client
                          ).addCallbacks(self._cbConnected, self._ebConnected)

    def callRemote(self, method, *args, **kw):
        if self.reference:
            return apply(self.reference.callRemote, (method,)+args, kw)
        if not self.connecting:
            self.startConnecting()
            self.connecting = True
        defr = defer.Deferred()
        self.methodsToCall.append((method, args, kw, defr))
        return defr

