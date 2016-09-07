# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces for L{twisted.mail}.

@since: 16.5
"""

from __future__ import absolute_import, division

from zope.interface import Interface


class IClientAuthentication(Interface):

    def getName():
        """
        Return an identifier associated with this authentication scheme.

        @rtype: C{bytes}
        """

    def challengeResponse(secret, challenge):
        """
        Generate a challenge response string.
        """



class IMessageDelivery(Interface):

    def receivedHeader(helo, origin, recipients):
        """
        Generate the Received header for a message.

        @type helo: 2-L{tuple} of L{bytes} and L{bytes}.
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: L{Address}
        @param origin: The address the message is from

        @type recipients: L{list} of L{User}
        @param recipients: A list of the addresses for which this message
        is bound.

        @rtype: L{bytes}
        @return: The full C{"Received"} header string.
        """

    def validateTo(user):
        """
        Validate the address for which the message is destined.

        @type user: L{User}
        @param user: The address to validate.

        @rtype: no-argument callable
        @return: A L{Deferred} which becomes, or a callable which takes no
            arguments and returns an object implementing L{IMessageSMTP}. This
            will be called and the returned object used to deliver the message
            when it arrives.

        @raise SMTPBadRcpt: Raised if messages to the address are not to be
            accepted.
        """

    def validateFrom(helo, origin):
        """
        Validate the address from which the message originates.

        @type helo: 2-L{tuple} of L{bytes} and L{bytes}.
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: L{Address}
        @param origin: The address the message is from

        @rtype: L{Deferred} or L{Address}
        @return: C{origin} or a L{Deferred} whose callback will be
        passed C{origin}.

        @raise SMTPBadSender: Raised of messages from this address are
        not to be accepted.
        """



class IMessageDeliveryFactory(Interface):
    """
    An alternate interface to implement for handling message delivery.

    It is useful to implement this interface instead of L{IMessageDelivery}
    directly because it allows the implementor to distinguish between different
    messages delivery over the same connection. This can be used to optimize
    delivery of a single message to multiple recipients, something which cannot
    be done by L{IMessageDelivery} implementors due to their lack of
    information.
    """
    def getMessageDelivery():
        """
        Return an L{IMessageDelivery} object.

        This will be called once per message.
        """



class IMessageSMTP(Interface):
    """
    Interface definition for messages that can be sent via SMTP.
    """

    def lineReceived(line):
        """
        Handle another line.
        """

    def eomReceived():
        """
        Handle end of message.

        return a deferred. The deferred should be called with either:
        callback(string) or errback(error)

        @rtype: L{Deferred}
        """

    def connectionLost():
        """
        Handle message truncated.

        semantics should be to discard the message
        """



__all__ = [
    # SMTP
    'IMessageDelivery', 'IMessageDeliveryFactory', 'IMessageSMTP',

    # Authentication
    'IClientAuthentication',
]
