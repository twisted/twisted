#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Simple IMAP4rev1 server
"""

from twisted.mail import imap4
from twisted.internet import reactor, defer, protocol
from zope.interface import implements
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse


class SimpleMailbox:
    implements(imap4.IMailbox, imap4.ICloseableMailbox)

    flags = ('\\Seen', '\\Answered', '\\Flagged',
             '\\Deleted', '\\Draft', '\\Recent', 'List')
    messages = []
    mUID = 0
    rw = 1
    closed = False

    def __init__(self):
        self.listeners = []
        self.addListener = self.listeners.append
        self.removeListener = self.listeners.remove

    def getFlags(self):
        return self.flags

    def getHierarchicalDelimiter(self):
        return '/'

    def getUIDValidity(self):
        pass
        #return 42

    def getUIDNext(self):
        pass
        #return len(self.messages) + 1

    def getUID(self, message):
        pass

    def getMessageCount(self):
        return 9

    def getRecentCount(self):
        #return 3
        pass

    def getUnseenCount(self):
        return 4

    def isWriteable(self):
        pass
        #return self.rw

    def destroy(self):
        pass

    def requestStatus(self, names):
        r = {}
        if 'MESSAGES' in names:
            r['MESSAGES'] = self.getMessageCount()
        if 'UNSEEN' in names:
            r['UNSEEN'] = self.getUnseenCount()
        return defer.succeed(r)

    def addListener(self, listener):
        pass

    def removeListener(self, listener):
        pass

    def addMessage(self, message, flags, date = None):
        pass

    def expunge(self):
        pass

    def fetch(self, messages, uid = False):
        pass

    def store(self, messages, flags, mode, uid):
        pass

    def close(self):
        self.closed = True


class Account(imap4.MemoryAccount):
    mailboxFactory = SimpleMailbox

    def __init__(self, name):
        imap4.MemoryAccount.__init__(self, name)
        # let's create the default mailbox Index
        if 'Index' not in self.mailboxes:
            self.create("Inbox")


    def _emptyMailbox(self, name, id):
        return self.mailboxFactory()


    """
    def select(self, name, rw=1):
        mbox = imap4.MemoryAccount.select(self, name)
        if mbox is not None:
            mbox.rw = rw
        return mbox
    """



class MailUserRealm(object):
    implements(IRealm)

    avatarInterfaces = {
        imap4.IAccount: Account,
    }

    def requestAvatar(self, avatarId, mind, *interfaces):
        for requestedInterface in interfaces:
            if self.avatarInterfaces.has_key(requestedInterface):
                # return an instance of the correct class
                avatarClass = self.avatarInterfaces[requestedInterface]
                avatar = avatarClass("testuser")
                # null logout function: take no arguments and do nothing
                logout = lambda: None
                return defer.succeed((requestedInterface, avatar, logout))

        # none of the requested interfaces was supported
        raise KeyError("None of the requested interfaces is supported")


class IMAPServerProtocol(imap4.IMAP4Server):
    "Subclass of imap4.IMAP4Server that adds debugging."
    debug = True


    def __init__(self, portal, *args, **kw):
        imap4.IMAP4Server.__init__(self, *args, **kw)
        self.portal = portal
        self.timeoutTest = False


    def lineReceived(self, line):
        if self.debug:
            print "CLIENT:", line
        imap4.IMAP4Server.lineReceived(self, line)


    def sendLine(self, line):
        imap4.IMAP4Server.sendLine(self, line)
        if self.debug:
            print "SERVER:", line



class IMAPFactory(protocol.Factory):
    protocol = IMAPServerProtocol
    portal = None # placeholder

    def buildProtocol(self, address):
        p = self.protocol(self.portal)
        p.factory = self
        return p



if __name__ == "__main__":
    portal = Portal(MailUserRealm())
    checker = InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("testuser", "password")
    portal.registerChecker(checker)

    factory = IMAPFactory()
    factory.portal = portal

    reactor.listenTCP(1143, factory)
    print "IMAP Server is Listening on TCP 1143..."
    reactor.run()
