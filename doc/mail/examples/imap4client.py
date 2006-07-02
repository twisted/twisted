#!/usr/bin/python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Simple IMAP4 client which displays the subjects of all messages in a 
particular mailbox.
"""

import sys

from twisted.internet import protocol
from twisted.internet import ssl
from twisted.internet import defer
from twisted.internet import stdio
from twisted.mail import imap4
from twisted.protocols import basic
from twisted.python import util
from twisted.python import log

class TrivialPrompter(basic.LineReceiver):
    from os import linesep as delimiter

    promptDeferred = None
    
    def prompt(self, msg):
        assert self.promptDeferred is None
        self.display(msg)
        self.promptDeferred = defer.Deferred()
        return self.promptDeferred
    
    def display(self, msg):
        self.transport.write(msg)
    
    def lineReceived(self, line):    
        if self.promptDeferred is None:
            return
        d, self.promptDeferred = self.promptDeferred, None
        d.callback(line)

class SimpleIMAP4Client(imap4.IMAP4Client):
    greetDeferred = None
    
    def serverGreeting(self, caps):
        self.serverCapabilities = caps
        if self.greetDeferred is not None:
            d, self.greetDeferred = self.greetDeferred, None
            d.callback(self)

class SimpleIMAP4ClientFactory(protocol.ClientFactory):
    usedUp = False

    protocol = SimpleIMAP4Client

    def __init__(self, username, onConn):
        self.ctx = ssl.ClientContextFactory()
        
        self.username = username
        self.onConn = onConn

    def buildProtocol(self, addr):
        assert not self.usedUp
        self.usedUp = True
        
        p = self.protocol(self.ctx)
        p.factory = self
        p.greetDeferred = self.onConn

        auth = imap4.CramMD5ClientAuthenticator(self.username)
        p.registerAuthenticator(auth)
        
        return p
    
    def clientConnectionFailed(self, connector, reason):
        d, self.onConn = self.onConn, None
        d.errback(reason)

# Initial callback - invoked after the server sends us its greet message
def cbServerGreeting(proto, username, password):
    # Hook up stdio
    tp = TrivialPrompter()
    stdio.StandardIO(tp)
    
    # And make it easily accessible
    proto.prompt = tp.prompt
    proto.display = tp.display

    # Try to authenticate securely
    return proto.authenticate(password
        ).addCallback(cbAuthentication, proto
        ).addErrback(ebAuthentication, proto, username, password
        )

# Fallback error-handler.  If anything goes wrong, log it and quit.
def ebConnection(reason):
    log.startLogging(sys.stdout)
    log.err(reason)
    from twisted.internet import reactor
    reactor.stop()

# Callback after authentication has succeeded
def cbAuthentication(result, proto):
    # List a bunch of mailboxes
    return proto.list("", "*"
        ).addCallback(cbMailboxList, proto
        )

# Errback invoked when authentication fails
def ebAuthentication(failure, proto, username, password):
    # If it failed because no SASL mechanisms match, offer the user the choice
    # of logging in insecurely.
    failure.trap(imap4.NoSupportedAuthentication)
    return proto.prompt("No secure authentication available.  Login insecurely? (y/N) "
        ).addCallback(cbInsecureLogin, proto, username, password
        )

# Callback for "insecure-login" prompt
def cbInsecureLogin(result, proto, username, password):
    if result.lower() == "y":
        # If they said yes, do it.
        return proto.login(username, password
            ).addCallback(cbAuthentication, proto
            )
    return defer.fail(Exception("Login failed for security reasons."))

# Callback invoked when a list of mailboxes has been retrieved
def cbMailboxList(result, proto):
    result = [e[2] for e in result]
    s = '\n'.join(['%d. %s' % (n + 1, m) for (n, m) in zip(range(len(result)), result)])
    if not s:
        return defer.fail(Exception("No mailboxes exist on server!"))
    return proto.prompt(s + "\nWhich mailbox? [1] "
        ).addCallback(cbPickMailbox, proto, result
        )

# When the user selects a mailbox, "examine" it.
def cbPickMailbox(result, proto, mboxes):
    mbox = mboxes[int(result or '1') - 1]
    return proto.examine(mbox
        ).addCallback(cbExamineMbox, proto
        )

# Callback invoked when examine command completes.
def cbExamineMbox(result, proto):
    # Retrieve the subject header of every message on the mailbox.
    return proto.fetchSpecific('1:*',
                               headerType='HEADER.FIELDS',
                               headerArgs=['SUBJECT']
        ).addCallback(cbFetch, proto
        )

# Finally, display headers.
def cbFetch(result, proto):
    keys = result.keys()
    keys.sort()
    for k in keys:
        proto.display('%s %s' % (k, result[k][0][2]))
    return proto.logout()

PORT = 143

def main():
    hostname = raw_input('IMAP4 Server Hostname: ')
    username = raw_input('IMAP4 Username: ')
    password = util.getPassword('IMAP4 Password: ')
    
    onConn = defer.Deferred(
        ).addCallback(cbServerGreeting, username, password
        ).addErrback(ebConnection
        )

    factory = SimpleIMAP4ClientFactory(username, onConn)
    
    from twisted.internet import reactor
    conn = reactor.connectTCP(hostname, PORT, factory)
    reactor.run()

if __name__ == '__main__':
    main()
