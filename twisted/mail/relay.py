
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Support for relaying mail for twisted.mail"""

from twisted.protocols import smtp
import os, time, cPickle

class DomainPickler:

    """An SMTP domain which keeps relayable pickles of all messages"""

    def __init__(self, path):
        """Initialize

        First argument is the directory in which pickles are kept
        """
        self.path = path
        self.n = 0

    def exists(self, user, success, failure):
        """Check whether we will relay

        Call overridable willRelay method
        """
        if self.willRelay(user.protocol):
            success(user)
        else:
            failure(user)

    def willRelay(self, protocol):
        """Check whether we agree to relay

        The default is to relay for non-inet connections or for
        localhost inet connections. Note that this means we are
        an open IPv6 relay
        """
        peer = protocol.transport.getPeer()
        return peer[0] != 'INET' or peer[1] == '127.0.0.1'

    def saveMessage(self, user, message):
        """save a relayable pickle of the message

        The filename is uniquely chosen.
        The pickle contains a tuple: from, to, message
        """
        fname = "%s_%s_%s" % (os.getpid(), time.time(), self.n)
        self.n = self.n+1
        fp = open(os.path.join(self.path, fname), 'w')
        try:
            cPickle.dump((user.orig, '%s@%s' % (user.name, user.domain), 
                                             message), fp)
        finally:
            fp.close()


class SMTPRelayer(smtp.SMTPClient):

    def __init__(self, messages):
        self.messages = []
        for message in messages:
            fp = open(message)
            try:
                messageContents = cPickle.load(fp)
            finally:
                fp.close()
            self.messages.append((message, messageContents))

    def getMailFrom(self):
        if not self.messages:
            return None
        return self.messages[0][1][0]

    def getMailTo(self):
        return [self.messages[0][1][1]]

    def getMailData(self):
        return self.messages[0][1][2]

    def sentMail(self, addresses):
        if addresses:
            os.remove(self.messages[0][0])
        del self.messages[0]
