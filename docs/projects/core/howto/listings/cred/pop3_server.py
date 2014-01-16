# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import Interface

from twisted.protocols import basic
from twisted.python import log
from twisted.cred import credentials, error
from twisted.internet import defer

class IMailbox(Interface):
    """
    Interface specification for mailbox.
    """
    def deleteMessage(index):
        pass


class POP3(basic.LineReceiver):
    # ...
    def __init__(self, portal):
        self.portal = portal

    def do_DELE(self, i):
        # uses self.mbox, which is set after login
        i = int(i)-1
        self.mbox.deleteMessage(i)
        self.successResponse()

    def do_USER(self, user):
        self._userIs = user
        self.successResponse('USER accepted, send PASS')

    def do_PASS(self, password):
        if self._userIs is None:
            self.failResponse("USER required before PASS")
            return
        user = self._userIs
        self._userIs = None
        d = defer.maybeDeferred(self.authenticateUserPASS, user, password)
        d.addCallback(self._cbMailbox, user)

    def authenticateUserPASS(self, user, password):
        if self.portal is not None:
            return self.portal.login(
                credentials.UsernamePassword(user, password),
                None,
                IMailbox
            )
        raise error.UnauthorizedLogin()

    def _cbMailbox(self, ial, user):
        interface, avatar, logout = ial

        if interface is not IMailbox:
            self.failResponse('Authentication failed')
            log.err("_cbMailbox() called with an interface other than IMailbox")
            return

        self.mbox = avatar
        self._onLogout = logout
        self.successResponse('Authentication succeeded')
        log.msg("Authenticated login for " + user)
