from twisted.python import log
from twisted.persisted import styles

class IoHandle(log.Logger, styles.Ephemeral):
    def __init__(self, reactor=None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor

