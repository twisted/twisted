# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

"""
Persistent references for PB.

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}

Stability: in flux

Future Plans: PerspectiveConnector should be made obsolete by PB URLs.  It
should be very easy to replace when that new functionality is available.

"""


from twisted.spread import pb
from twisted.internet import defer
from twisted.python import log

True = 1
False = 0

# "Sturdy" references in PB

class PerspectiveConnector:
    def __init__(self, host, port, username, password, serviceName,
                 perspectiveName=None, client=None):
        # perspective-specific stuff
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.serviceName = serviceName
        self.perspectiveName = perspectiveName
        self.client = client
        # remote-reference-type-neutral stuff
        self.reference = None
        self.connecting = False
        self.methodsToCall = []

    def __getstate__(self):
        d = self.__dict__.copy()
        d['reference'] = None
        d['connecting'] = False
        d['methodsToCall'] = []
        return d

    def _cbConnected(self, reference):
        """We've connected.  Reset everything and call all pending methods.
        """
        log.msg( 'connected!' )
        self.reference = reference
        self.connecting = False
        for method, args, kw, defr in self.methodsToCall:
            apply(reference.callRemote, (method,)+args, kw).addCallbacks(
                defr.callback,
                defr.errback)
        self.methodsToCall = []

    def _ebConnected(self, error):
        """We haven't connected yet.  Try again.
        """
        log.msg( 'PerspectiveConnector: error in connecting: %s' % error)
        self.startConnecting()

    def startConnecting(self):
        log.msg( 'PerspectiveConnector: connecting: %s:%s %s/%s/%s' % (self.host, self.port, self.serviceName, self.username, self.perspectiveName))
        return pb.connect(self.host, self.port, self.username, self.password,
                          self.serviceName, self.perspectiveName, self.client
                          ).addCallbacks(self._cbConnected, self._ebConnected)

    def callRemote(self, method, *args, **kw):
        if self.reference:
            try:
                return apply(self.reference.callRemote, (method,)+args, kw)
            except pb.DeadReferenceError:
                log.msg("Calling dead reference; trying to reconnect.")
                self.reference = None
        if not self.connecting:
            self.startConnecting()
            self.connecting = True
        defr = defer.Deferred()
        self.methodsToCall.append((method, args, kw, defr))
        return defr

