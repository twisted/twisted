# -*- test-case-name: twisted.test.test_ident -*-
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

"""
Ident protocol implementation.

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

from twisted.internet import defer
from twisted.protocols import basic
from twisted.python import log

class IdentError(Exception):
    """
    Can't determine connection owner; reason unknown.
    """
    
    identDescription = 'UNKNOWN-ERROR'

    def __str__(self):
        return self.identDescription


class NoUser(IdentError):
    """
    The connection specified by the port pair is not currently in use or
    currently not owned by an identifiable entity.
    """
    identDescription = 'NO-USER'


class InvalidPort(IdentError):
    """
    Either the local or foreign port was improperly specified. This should
    be returned if either or both of the port ids were out of range (TCP
    port numbers are from 1-65535), negative integers, reals or in any
    fashion not recognized as a non-negative integer.
    """
    identDescription = 'INVALID-PORT'


class HiddenUser(IdentError):
    """
    The server was able to identify the user of this port, but the
    information was not returned at the request of the user.
    """
    identDescription = 'HIDDEN-USER'


class IdentServer(basic.LineOnlyReceiver):
    """
    The Identification Protocol (a.k.a., "ident", a.k.a., "the Ident
    Protocol") provides a means to determine the identity of a user of a
    particular TCP connection. Given a TCP port number pair, it returns a
    character string which identifies the owner of that connection on the
    server's system.
    
    Server authors should subclass this class and override the lookup method.
    The default implementation returns an UNKNOWN-ERROR response for every
    query.
    """

    def lineReceived(self, line):
        parts = line.split(',')
        if len(parts) != 2:
            self.invalidQuery()
        else:
            try:
                portOnServer, portOnClient = map(int, parts)
            except ValueError:
                self.invalidQuery()
            else:
                self.validQuery(portOnServer, portOnClient)
    
    def invalidQuery(self):
        self.transport.loseConnection()
    
    def validQuery(self, portOnServer, portOnClient):
        serverAddr = self.transport.getHost()[1], portOnServer
        clientAddr = self.transport.getPeer()[1], portOnClient
        defer.maybeDeferred(self.lookup, serverAddr, clientAddr
            ).addCallback(self._cbLookup, portOnServer, portOnClient
            ).addErrback(self._ebLookup, portOnServer, portOnClient
#            ).addErrback(log.err
            )
    
    def _cbLookup(self, (sysName, userId), sport, cport):
        self.sendLine('%d, %d : USERID : %s : %s' % (sport, cport, sysName, userId))

    def _ebLookup(self, failure, sport, cport):
        if failure.check(IdentError):
            self.sendLine('%d, %d : ERROR : %s' % (sport, cport, failure.value))
        else:
            log.err(failure)
            self.sendLine('%d, %d : ERROR : %s' % (sport, cport, IdentError(failure.value)))
 
    def lookup(self, serverAddress, clientAddress):
        """Lookup user information about the specified address pair.
        
        Return value should be a two-tuple of system name and username. 
        Acceptable values for the system name may be found in the "SYSTEM
        NAMES" section of RFC 1340 or its successor.
        
        This method may also raise any IdentError subclass (or IdentError
        itself) to indicate user information will not be provided for the
        given query.
        
        A Deferred may also be returned.
        """
        raise IdentError()


class IdentClient(basic.LineOnlyReceiver):

    errorTypes = (IdentError, NoUser, InvalidPort, HiddenUser)

    def __init__(self):
        self.queries = []
    
    def lookup(self, portOnServer, portOnClient):
        """Lookup user information about the specified address pair.
        """
        self.queries.append((defer.Deferred(), portOnServer, portOnClient))
        if len(self.queries) > 1:
            return self.queries[-1][0]
        
        self.sendLine('%d, %d' % (portOnServer, portOnClient))
        return self.queries[-1][0]

    def lineReceived(self, line):
        if not self.queries:
            log.msg("Unexpected server response: %r" % (line,))
        else:
            d, _, _ = self.queries.pop(0)
            self.parseResponse(d, line)
            if self.queries:
                self.sendLine('%d, %d' % (self.queries[0][1], self.queries[0][2]))

    def connectionLost(self, reason):
        for q in self.queries:
            q[0].errback(IdentError(reason))
        self.queries = []
    
    def parseResponse(self, deferred, line):
        parts = line.split(':', 2)
        if len(parts) != 3:
            deferred.errback(IdentError(line))
        else:
            ports, type, addInfo = map(str.strip, parts)
            if type == 'ERROR':
                for et in self.errorTypes:
                    if et.identDescription == addInfo:
                        deferred.errback(et(line))
                        return
                deferred.errback(IdentError(line))
            else:
                deferred.callback((type, addInfo))
