

from twisted.spread.pb import PBClientFactory
from twisted.internet import protocol
from twisted.python import log

class ReconnectingPBClientFactory(PBClientFactory,
                                  protocol.ReconnectingClientFactory):
    """Reconnecting client factory for PB brokers.

    Like PBClientFactory, but if the connection fails or is lost, the factory
    will attempt to reconnect.

    Instead of using getRootObject (which gives a Deferred that can only be
    fired once), override the gotRootObject method.

    When using login, override the gotPerspective method instead of using the
    Deferred.

    gotRootObject and gotPerspective will be called each time the object is
    received (once per successful connection attempt). You will probably want
    to use obj.notifyOnDisconnect to find out when the connection is lost.

    If an authorization error occurs, failedToGetPerspective() will be
    invoked.

    getPerspective() is disabled: this class offers newcred access only.
    """

    def __init__(self):
        PBClientFactory.__init__(self)
        self.doingLogin = False

    def clientConnectionFailed(self, connector, reason):
        PBClientFactory.clientConnectionFailed(self, connector, reason)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, reason):
        PBClientFactory.clientConnectionLost(self, connector, reason,
                                             reconnecting=True)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionLost(self, connector, reason)

    def clientConnectionMade(self, broker):
        self.resetDelay()
        PBClientFactory.clientConnectionMade(self, broker)
        if self.doingLogin:
            self.doLogin()
        self.gotRootObject(self._root)

    def gotRootObject(self, root):
        """The remote root object (obtained each time this factory connects)
        is now available. This method will be called each time the connection
        is established and the object reference is retrieved."""
        pass

    def getPerspective(self, *args):
        raise RuntimeError, "ReconnectingPBClientFactory does not support getPerspective: use login instead"

    def doLogin(self):
        root = self._root
        d = self._cbSendUsername(self._root, self.credentials.username,
                                 self.credentials.password, self.client)
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective)

    def gotPerspective(self, perspective):
        """The remote avatar (obtained each time this factory connects) is
        now available."""
        pass

    def failedToGetPerspective(self, why):
        self.stopTrying() # logging in harder won't help
        log.err(why)

    def login(self, credentials, client=None):
        self.credentials = credentials
        self.client = client
        self.doingLogin = True
