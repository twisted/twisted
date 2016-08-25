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



class IServerFactory(Interface):
    """
    An interface for querying capabilities of a POP3 server.

    Any cap_* method may raise L{NotImplementedError} if the particular
    capability is not supported.  If L{cap_EXPIRE()} does not raise
    L{NotImplementedError}, L{perUserExpiration()} must be implemented,
    otherwise they are optional.  If L{cap_LOGIN_DELAY()} is implemented,
    L{perUserLoginDelay()} must be implemented, otherwise they are optional.

    @type challengers: L{dict} of L{bytes} -> L{IUsernameHashedPassword
        <cred.credentials.IUsernameHashedPassword>}
    @ivar challengers: A mapping of challenger names to
        L{IUsernameHashedPassword <cred.credentials.IUsernameHashedPassword>}
        provider.
    """
    def cap_IMPLEMENTATION():
        """
        Return a string describing the POP3 server implementation.

        @rtype: L{bytes}
        @return: Server implementation information.
        """


    def cap_EXPIRE():
        """
        Return the minimum number of days messages are retained.

        @rtype: L{int} or L{None}
        @return: The minimum number of days messages are retained or none, if
            the server never deletes messages.
        """


    def perUserExpiration():
        """
        Indicate whether the message expiration policy differs per user.

        @rtype: L{bool}
        @return: C{True} when the message expiration policy differs per user,
            C{False} otherwise.
        """


    def cap_LOGIN_DELAY():
        """
        Return the minimum number of seconds between client logins.

        @rtype: L{int}
        @return: The minimum number of seconds between client logins.
        """


    def perUserLoginDelay():
        """
        Indicate whether the login delay period differs per user.

        @rtype: L{bool}
        @return: C{True} when the login delay differs per user, C{False}
            otherwise.
        """



class IMailbox(Interface):
    """
    An interface for mailbox access.

    Message indices are 0-based.

    @type loginDelay: L{int}
    @ivar loginDelay: The number of seconds between allowed logins for the
        user associated with this mailbox.

    @type messageExpiration: L{int}
    @ivar messageExpiration: The number of days messages in this mailbox will
        remain on the server before being deleted.
    """
    def listMessages(index=None):
        """
        Retrieve the size of a message, or, if none is specified, the size of
        each message in the mailbox.

        @type index: L{int} or L{None}
        @param index: The 0-based index of the message.

        @rtype: L{int}, sequence of L{int}, or L{Deferred <defer.Deferred>}
        @return: The number of octets in the specified message, or, if an
            index is not specified, a sequence of the number of octets for
            all messages in the mailbox or a deferred which fires with
            one of those. Any value which corresponds to a deleted message
            is set to 0.

        @raise ValueError or IndexError: When the index does not correspond to
            a message in the mailbox.  The use of ValueError is preferred.
        """


    def getMessage(index):
        """
        Retrieve a file containing the contents of a message.

        @type index: L{int}
        @param index: The 0-based index of a message.

        @rtype: file-like object
        @return: A file containing the message.

        @raise ValueError or IndexError: When the index does not correspond to
            a message in the mailbox.  The use of ValueError is preferred.
        """


    def getUidl(index):
        """
        Get a unique identifier for a message.

        @type index: L{int}
        @param index: The 0-based index of a message.

        @rtype: L{bytes}
        @return: A string of printable characters uniquely identifying the
            message for all time.

        @raise ValueError or IndexError: When the index does not correspond to
            a message in the mailbox.  The use of ValueError is preferred.
        """


    def deleteMessage(index):
        """
        Mark a message for deletion.

        This must not change the number of messages in this mailbox.  Further
        requests for the size of the deleted message should return 0.  Further
        requests for the message itself may raise an exception.

        @type index: L{int}
        @param index: The 0-based index of a message.

        @raise ValueError or IndexError: When the index does not correspond to
            a message in the mailbox.  The use of ValueError is preferred.
        """


    def undeleteMessages():
        """
        Undelete all messages marked for deletion.

        Any message which can be undeleted should be returned to its original
        position in the message sequence and retain its original UID.
        """


    def sync():
        """
        Discard the contents of any message marked for deletion.
        """


class IDomain(Interface):
    """
    An interface for email domains.
    """
    def exists(user):
        """
        Check whether a user exists in this domain.

        @type user: L{User}
        @param user: A user.

        @rtype: no-argument callable which returns L{IMessage} provider
        @return: A function which takes no arguments and returns a message
            receiver for the user.

        @raise SMTPBadRcpt: When the given user does not exist in this domain.
        """


    def addUser(user, password):
        """
        Add a user to this domain.

        @type user: L{bytes}
        @param user: A username.

        @type password: L{bytes}
        @param password: A password.
        """


    def getCredentialsCheckers():
        """
        Return credentials checkers for this domain.

        @rtype: L{list} of L{ICredentialsChecker
            <twisted.cred.checkers.ICredentialsChecker>} provider
        @return: Credentials checkers for this domain.
        """



class IAliasableDomain(IDomain):
    """
    An interface for email domains which can be aliased to other domains.
    """
    def setAliasGroup(aliases):
        """
        Set the group of defined aliases for this domain.

        @type aliases: L{dict} of L{bytes} -> L{IAlias} provider
        @param aliases: A mapping of domain name to alias.
        """


    def exists(user, memo=None):
        """
        Check whether a user exists in this domain or an alias of it.

        @type user: L{User}
        @param user: A user.

        @type memo: L{None} or L{dict} of L{AliasBase <twisted.mail.mail.AliasBase>}
        @param memo: A record of the addresses already considered while
            resolving aliases.  The default value should be used by all
            external code.

        @rtype: no-argument callable which returns L{IMessage} provider
        @return: A function which takes no arguments and returns a message
            receiver for the user.

        @raise SMTPBadRcpt: When the given user does not exist in this domain
            or an alias of it.
        """



class IMessageDelivery(Interface):

    def receivedHeader(helo, origin, recipients):
        """
        Generate the Received header for a message

        @type helo: C{(str, str)}
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: C{Address}
        @param origin: The address the message is from

        @type recipients: C{list} of L{User}
        @param recipients: A list of the addresses for which this message
        is bound.

        @rtype: C{str}
        @return: The full \"Received\" header string.
        """

    def validateTo(user):
        """
        Validate the address for which the message is destined.

        @type user: L{User}
        @param user: The address to validate.

        @rtype: no-argument callable
        @return: A C{Deferred} which becomes, or a callable which
        takes no arguments and returns an object implementing L{IMessage}.
        This will be called and the returned object used to deliver the
        message when it arrives.

        @raise SMTPBadRcpt: Raised if messages to the address are
        not to be accepted.
        """

    def validateFrom(helo, origin):
        """
        Validate the address from which the message originates.

        @type helo: C{(str, str)}
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: C{Address}
        @param origin: The address the message is from

        @rtype: C{Deferred} or C{Address}
        @return: C{origin} or a C{Deferred} whose callback will be
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



class IMessage(Interface):
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
