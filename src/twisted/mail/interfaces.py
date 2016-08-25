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



class IMailboxSMTP(Interface):
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

        @rtype: no-argument callable which returns L{IMessageSMTPI} provider
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



class IAlias(Interface):
    """
    An interface for aliases.
    """
    def createMessageReceiver():
        """
        Create a message receiver.

        @rtype: L{IMessageSMTP} provider
        @return: A message receiver.
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

        @type memo: L{None} or L{dict} of
            L{AliasBase <twisted.mail.alias.AliasBase>}
        @param memo: A record of the addresses already considered while
            resolving aliases. The default value should be used by all external
            code.

        @rtype: no-argument callable which returns L{IMessageSMTP} provider
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
        @return: A C{Deferred} which becomes, or a callable which takes no
            arguments and returns an object implementing L{IMessageSMTP}. This
            will be called and the returned object used to deliver the message
            when it arrives.

        @raise SMTPBadRcpt: Raised if messages to the address are not to be
            accepted.
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



class IMessageIMAPPart(Interface):
    def getHeaders(negate, *names):
        """
        Retrieve a group of message headers.

        @type names: C{tuple} of C{str}
        @param names: The names of the headers to retrieve or omit.

        @type negate: C{bool}
        @param negate: If True, indicates that the headers listed in C{names}
            should be omitted from the return value, rather than included.

        @rtype: C{dict}
        @return: A mapping of header field names to header field values
        """


    def getBodyFile():
        """
        Retrieve a file object containing only the body of this message.
        """


    def getSize():
        """
        Retrieve the total size, in octets, of this message.

        @rtype: C{int}
        """


    def isMultipart():
        """
        Indicate whether this message has subparts.

        @rtype: C{bool}
        """


    def getSubPart(part):
        """
        Retrieve a MIME sub-message

        @type part: C{int}
        @param part: The number of the part to retrieve, indexed from 0.

        @raise IndexError: Raised if the specified part does not exist.
        @raise TypeError: Raised if this message is not multipart.

        @rtype: Any object implementing L{IMessageIMAPPart}.
        @return: The specified sub-part.
        """



class IMessageIMAP(IMessageIMAPPart):

    def getUID():
        """
        Retrieve the unique identifier associated with this message.
        """


    def getFlags():
        """
        Retrieve the flags associated with this message.

        @rtype: C{iterable}
        @return: The flags, represented as strings.
        """


    def getInternalDate():
        """
        Retrieve the date internally associated with this message.

        @rtype: C{str}
        @return: An RFC822-formatted date string.
        """



class IMessageIMAPFile(Interface):
    """
    Optional message interface for representing messages as files.

    If provided by message objects, this interface will be used instead the
    more complex MIME-based interface.
    """

    def open():
        """
        Return a file-like object opened for reading.

        Reading from the returned file will return all the bytes of which this
        message consists.
        """



class ISearchableIMAPMailbox(Interface):

    def search(query, uid):
        """
        Search for messages that meet the given query criteria.

        If this interface is not implemented by the mailbox,
        L{IMailboxIMAP.fetch} and various methods of L{IMessageIMAP} will be
        used instead.

        Implementations which wish to offer better performance than the default
        implementation should implement this interface.

        @type query: C{list}
        @param query: The search criteria

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs; otherwise
            they are message sequence IDs.

        @rtype: C{list} or C{Deferred}
        @return: A list of message sequence numbers or message UIDs which match
            the search criteria or a C{Deferred} whose callback will be invoked
            with such a list.

        @raise IllegalQueryError: Raised when query is not valid.
        """



class IMailboxIMAPListener(Interface):
    """
    Interface for objects interested in mailbox events
    """

    def modeChanged(writeable):
        """
        Indicates that the write status of a mailbox has changed.

        @type writeable: C{bool}
        @param writeable: A true value if write is now allowed, false
            otherwise.
        """


    def flagsChanged(newFlags):
        """
        Indicates that the flags of one or more messages have changed.

        @type newFlags: C{dict}
        @param newFlags: A mapping of message identifiers to tuples of flags
            now set on that message.
        """


    def newMessages(exists, recent):
        """
        Indicates that the number of messages in a mailbox has changed.

        @type exists: C{int} or L{None}
        @param exists: The total number of messages now in this mailbox. If the
            total number of messages has not changed, this should be L{None}.

        @type recent: C{int}
        @param recent: The number of messages now flagged \\Recent. If the
            number of recent messages has not changed, this should be L{None}.
        """



class IMessageIMAPCopier(Interface):
    def copy(messageObject):
        """
        Copy the given message object into this mailbox.

        The message object will be one which was previously returned by
        L{IMailboxIMAP.fetch}.

        Implementations which wish to offer better performance than the default
        implementation should implement this interface.

        If this interface is not implemented by the mailbox,
        L{IMailboxIMAP.addMessage} will be used instead.

        @rtype: C{Deferred} or C{int}
        @return: Either the UID of the message or a Deferred which fires with
            the UID when the copy finishes.
        """



class IMailboxIMAPInfo(Interface):
    """
    Interface specifying only the methods required for C{listMailboxes}.

    Implementations can return objects implementing only these methods for
    return to C{listMailboxes} if it can allow them to operate more
    efficiently.
    """

    def getFlags():
        """
        Return the flags defined in this mailbox

        Flags with the \\ prefix are reserved for use as system flags.

        @rtype: C{list} of C{str}
        @return: A list of the flags that can be set on messages in this
            mailbox.
        """


    def getHierarchicalDelimiter():
        """
        Get the character which delimits namespaces for in this mailbox.

        @rtype: C{str}
        """



class IMailboxIMAP(IMailboxIMAPInfo):
    def getUIDValidity():
        """
        Return the unique validity identifier for this mailbox.

        @rtype: C{int}
        """


    def getUIDNext():
        """
        Return the likely UID for the next message added to this mailbox.

        @rtype: C{int}
        """


    def getUID(message):
        """
        Return the UID of a message in the mailbox

        @type message: C{int}
        @param message: The message sequence number

        @rtype: C{int}
        @return: The UID of the message.
        """


    def getMessageCount():
        """
        Return the number of messages in this mailbox.

        @rtype: C{int}
        """


    def getRecentCount():
        """
        Return the number of messages with the 'Recent' flag.

        @rtype: C{int}
        """


    def getUnseenCount():
        """
        Return the number of messages with the 'Unseen' flag.

        @rtype: C{int}
        """


    def isWriteable():
        """
        Get the read/write status of the mailbox.

        @rtype: C{int}
        @return: A true value if write permission is allowed, a false value
            otherwise.
        """


    def destroy():
        """
        Called before this mailbox is deleted, permanently.

        If necessary, all resources held by this mailbox should be cleaned up
        here. This function _must_ set the \\Noselect flag on this mailbox.
        """


    def requestStatus(names):
        """
        Return status information about this mailbox.

        Mailboxes which do not intend to do any special processing to generate
        the return value, C{statusRequestHelper} can be used to build the
        dictionary by calling the other interface methods which return the data
        for each name.

        @type names: Any iterable
        @param names: The status names to return information regarding. The
            possible values for each name are: MESSAGES, RECENT, UIDNEXT,
            UIDVALIDITY, UNSEEN.

        @rtype: C{dict} or C{Deferred}
        @return: A dictionary containing status information about the requested
            names is returned. If the process of looking this information up
            would be costly, a deferred whose callback will eventually be
            passed this dictionary is returned instead.
        """


    def addListener(listener):
        """
        Add a mailbox change listener

        @type listener: Any object which implements C{IMailboxIMAPListener}
        @param listener: An object to add to the set of those which will be
            notified when the contents of this mailbox change.
        """


    def removeListener(listener):
        """
        Remove a mailbox change listener

        @type listener: Any object previously added to and not removed from
            this mailbox as a listener.
        @param listener: The object to remove from the set of listeners.

        @raise ValueError: Raised when the given object is not a listener for
            this mailbox.
        """


    def addMessage(message, flags=(), date=None):
        """
        Add the given message to this mailbox.

        @type message: A file-like object
        @param message: The RFC822 formatted message

        @type flags: Any iterable of C{str}
        @param flags: The flags to associate with this message

        @type date: C{str}
        @param date: If specified, the date to associate with this message.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with the message id if
            the message is added successfully and whose errback is invoked
            otherwise.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
            read-write.
        """


    def expunge():
        """
        Remove all messages flagged \\Deleted.

        @rtype: C{list} or C{Deferred}
        @return: The list of message sequence numbers which were deleted, or a
            C{Deferred} whose callback will be invoked with such a list.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
            read-write.
        """


    def fetch(messages, uid):
        """
        Retrieve one or more messages.

        @type messages: C{MessageSet}
        @param messages: The identifiers of messages to retrieve information
            about

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs; otherwise
            they are message sequence IDs.

        @rtype: Any iterable of two-tuples of message sequence numbers and
            implementors of C{IMessageIMAP}.
        """


    def store(messages, flags, mode, uid):
        """
        Set the flags of one or more messages.

        @type messages: A MessageSet object with the list of messages requested
        @param messages: The identifiers of the messages to set the flags of.

        @type flags: sequence of C{str}
        @param flags: The flags to set, unset, or add.

        @type mode: -1, 0, or 1
        @param mode: If mode is -1, these flags should be removed from the
            specified messages. If mode is 1, these flags should be added to
            the specified messages. If mode is 0, all existing flags should be
            cleared and these flags should be added.

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs; otherwise
            they are message sequence IDs.

        @rtype: C{dict} or C{Deferred}
        @return: A C{dict} mapping message sequence numbers to sequences of
            C{str} representing the flags set on the message after this
            operation has been performed, or a C{Deferred} whose callback will
            be invoked with such a C{dict}.

        @raise ReadOnlyMailbox: Raised if this mailbox is not open for
            read-write.
        """



class ICloseableMailboxIMAP(Interface):
    """
    A supplementary interface for mailboxes which require cleanup on close.

    Implementing this interface is optional. If it is implemented, the protocol
    code will call the close method defined whenever a mailbox is closed.
    """

    def close():
        """
        Close this mailbox.

        @return: A C{Deferred} which fires when this mailbox has been closed,
            or None if the mailbox can be closed immediately.
        """
