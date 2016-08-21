#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Simple IMAP4 client which displays the subjects of all messages in a
particular mailbox.
"""

from __future__ import print_function

import sys

from twisted.internet import endpoints
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
    """
    A client with callbacks for greeting messages from an IMAP server.
    """
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
        self.username = username
        self.onConn = onConn


    def buildProtocol(self, addr):
        """
        Initiate the protocol instance. Since we are building a simple IMAP
        client, we don't bother checking what capabilities the server has. We
        just add all the authenticators twisted.mail has.  Note: Gmail no
        longer uses any of the methods below, it's been using XOAUTH since
        2010.
        """
        assert not self.usedUp
        self.usedUp = True

        p = self.protocol()
        p.factory = self
        p.greetDeferred = self.onConn

        p.registerAuthenticator(imap4.PLAINAuthenticator(self.username))
        p.registerAuthenticator(imap4.LOGINAuthenticator(self.username))
        p.registerAuthenticator(
                imap4.CramMD5ClientAuthenticator(self.username))

        return p


    def clientConnectionFailed(self, connector, reason):
        d, self.onConn = self.onConn, None
        d.errback(reason)



def cbServerGreeting(proto, username, password):
    """
    Initial callback - invoked after the server sends us its greet message.
    """
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


def ebConnection(reason):
    """
    Fallback error-handler. If anything goes wrong, log it and quit.
    """
    log.startLogging(sys.stdout)
    log.err(reason)
    return reason


def cbAuthentication(result, proto):
    """
    Callback after authentication has succeeded.

    Lists a bunch of mailboxes.
    """
    return proto.list("", "*"
        ).addCallback(cbMailboxList, proto
        )


def ebAuthentication(failure, proto, username, password):
    """
    Errback invoked when authentication fails.

    If it failed because no SASL mechanisms match, offer the user the choice
    of logging in insecurely.

    If you are trying to connect to your Gmail account, you will be here!
    """
    failure.trap(imap4.NoSupportedAuthentication)
    return proto.prompt(
        "No secure authentication available. Login insecurely? (y/N) "
        ).addCallback(cbInsecureLogin, proto, username, password
        )


def cbInsecureLogin(result, proto, username, password):
    """
    Callback for "insecure-login" prompt.
    """
    if result.lower() == "y":
        # If they said yes, do it.
        return proto.login(username, password
            ).addCallback(cbAuthentication, proto
            )
    return defer.fail(Exception("Login failed for security reasons."))


def cbMailboxList(result, proto):
    """
    Callback invoked when a list of mailboxes has been retrieved.
    """
    result = [e[2] for e in result]
    s = '\n'.join(['%d. %s' % (n + 1, m) for (n, m) in zip(range(len(result)), result)])
    if not s:
        return defer.fail(Exception("No mailboxes exist on server!"))
    return proto.prompt(s + "\nWhich mailbox? [1] "
        ).addCallback(cbPickMailbox, proto, result
        )


def cbPickMailbox(result, proto, mboxes):
    """
    When the user selects a mailbox, "examine" it.
    """
    mbox = mboxes[int(result or '1') - 1]
    return proto.examine(mbox
        ).addCallback(cbExamineMbox, proto
        )


def cbExamineMbox(result, proto):
    """
    Callback invoked when examine command completes.

    Retrieve the subject header of every message in the mailbox.
    """
    return proto.fetchSpecific('1:*',
                               headerType='HEADER.FIELDS',
                               headerArgs=['SUBJECT'],
        ).addCallback(cbFetch, proto
        )


def cbFetch(result, proto):
    """
    Finally, display headers.
    """
    if result:
        keys = result.keys()
        keys.sort()
        for k in keys:
            proto.display('%s %s' % (k, result[k][0][2]))
    else:
        print("Hey, an empty mailbox!")

    return proto.logout()


def cbClose(result):
    """
    Close the connection when we finish everything.
    """
    from twisted.internet import reactor
    reactor.stop()


def main():
    hostname = raw_input('IMAP4 Server Hostname: ')
    port = raw_input('IMAP4 Server Port (the default is 143, 993 uses SSL): ')
    username = raw_input('IMAP4 Username: ')
    password = util.getPassword('IMAP4 Password: ')

    onConn = defer.Deferred(
        ).addCallback(cbServerGreeting, username, password
        ).addErrback(ebConnection
        ).addBoth(cbClose)

    factory = SimpleIMAP4ClientFactory(username, onConn)

    if not port:
        port = 143
    else:
        port = int(port)

    from twisted.internet import reactor

    endpoint = endpoints.HostnameEndpoint(reactor, hostname, port)

    if port == 993:
        contextFactory = ssl.optionsForClientTLS(
            hostname=hostname.decode('utf-8')
        )
        endpoint = endpoints.wrapClientTLS(contextFactory, endpoint)

    endpoint.connect(factory)
    reactor.run()


if __name__ == '__main__':
    main()
