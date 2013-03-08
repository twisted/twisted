# -*- test-case-name: twisted.test.test_postfix -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Postfix mail transport agent related protocols.
"""

import sys
import UserDict
import urllib

from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import protocol, defer
from twisted.python import log

# urllib's quote functions just happen to match
# the postfix semantics.
def quote(s):
    return urllib.quote(s)

def unquote(s):
    return urllib.unquote(s)

class PostfixTCPMapServer(basic.LineReceiver, policies.TimeoutMixin):
    """Postfix mail transport agent TCP map protocol implementation.

    Receive requests for data matching given key via lineReceived,
    asks it's factory for the data with self.factory.get(key), and
    returns the data to the requester. None means no entry found.

    You can use postfix's postmap to test the map service::

    /usr/sbin/postmap -q KEY tcp:localhost:4242

    """

    timeout = 600
    delimiter = '\n'

    def connectionMade(self):
        self.setTimeout(self.timeout)

    def sendCode(self, code, message=''):
        "Send an SMTP-like code with a message."
        self.sendLine('%3.3d %s' % (code, message or ''))

    def lineReceived(self, line):
        self.resetTimeout()
        try:
            request, params = line.split(None, 1)
        except ValueError:
            request = line
            params = None
        try:
            f = getattr(self, 'do_' + request)
        except AttributeError:
            self.sendCode(400, 'unknown command')
        else:
            try:
                f(params)
            except:
                self.sendCode(400, 'Command %r failed: %s.' % (request, sys.exc_info()[1]))

    def do_get(self, key):
        if key is None:
            self.sendCode(400, 'Command %r takes 1 parameters.' % 'get')
        else:
            d = defer.maybeDeferred(self.factory.get, key)
            d.addCallbacks(self._cbGot, self._cbNot)
            d.addErrback(log.err)

    def _cbNot(self, fail):
        self.sendCode(400, fail.getErrorMessage())

    def _cbGot(self, value):
        if value is None:
            self.sendCode(500)
        else:
            self.sendCode(200, quote(value))

    def do_put(self, keyAndValue):
        if keyAndValue is None:
            self.sendCode(400, 'Command %r takes 2 parameters.' % 'put')
        else:
            try:
                key, value = keyAndValue.split(None, 1)
            except ValueError:
                self.sendCode(400, 'Command %r takes 2 parameters.' % 'put')
            else:
                self.sendCode(500, 'put is not implemented yet.')


class PostfixTCPMapDictServerFactory(protocol.ServerFactory,
                                     UserDict.UserDict):
    """An in-memory dictionary factory for PostfixTCPMapServer."""

    protocol = PostfixTCPMapServer

class PostfixTCPMapDeferringDictServerFactory(protocol.ServerFactory):
    """An in-memory dictionary factory for PostfixTCPMapServer."""

    protocol = PostfixTCPMapServer

    def __init__(self, data=None):
        self.data = {}
        if data is not None:
            self.data.update(data)

    def get(self, key):
        return defer.succeed(self.data.get(key))
