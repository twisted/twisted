# -*- test-case-name: twisted.conch.test.test_address -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Address object for SSH network connections.

Maintainer: Paul Swartz

@since: 12.1
"""
from zope.interface import implements
from twisted.internet.interfaces import IAddress
from twisted.python import util



class SSHTransportAddress(object, util.FancyEqMixin):
    """
    Object representing an SSH Transport endpoint.

    @ivar address: A instance of an object which implements I{IAddress} to
        which this transport address is connected.
    """

    implements(IAddress)

    compareAttributes = ('address',)

    def __init__(self, address):
        self.address = address

    def __repr__(self):
        return 'SSHTransportAddress(%r)' % (self.address,)

    def __hash__(self):
        return hash(('SSH', self.address))

