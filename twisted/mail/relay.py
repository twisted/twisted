"""Support for relaying mail for twisted.mail"""

import os, time, cPickle

class DomainPickler:

    """An SMTP domain which keeps relayable pickles of all messages"""

    def __init__(self, path):
        """Initialize

        First argument is the directory in which pickles are kept
        """
        self.path = path
        self.n = 0

    def exists(self, user, domain):
        """Check whether we will relay

        Call overridable willRelay method
        """
        return self.willRelay()

    def willRelay(self):
        """Check whether we agree to relay

        The default is to relay for non-inet connections or for
        localhost inet connections. Note that this means we are
        an open IPv6 relay
        """
        peer = self.transport.getPeer()
        return peer[0] != 'INET' or peer[1] == '127.0.0.1'

    def saveMessage(self, origin, name, message, domain):
        """save a relayable pickle of the message

        The filename is uniquely chosen.
        The pickle contains a tuple: from, to, message
        """
        fname = "%s_%s_%s" % (os.getpid(), os.time(), self.n)
        self.n = self.n+1
        fp = open(os.path.join(self.path, fname), 'w')
        try:
            cPickle.dump((origin, '%s@%s' % (name, domain), message), fp)
        finally:
            fp.close()
