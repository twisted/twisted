from twisted.python import log
from twisted.persisted import styles
from twisted.internet import interfaces

class IoHandle(log.Logger, styles.Ephemeral):
    __implements__ = (interfaces.ITransport,)

    def __init__(self, reactor=None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor

