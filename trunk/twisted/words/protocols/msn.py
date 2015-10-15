# -*- test-case-name: twisted.words.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
MSNP8 Protocol (client only) - semi-experimental

This module provides support for clients using the MSN Protocol (MSNP8).
There are basically 3 servers involved in any MSN session:

I{Dispatch server}

The DispatchClient class handles connections to the
dispatch server, which basically delegates users to a
suitable notification server.

You will want to subclass this and handle the gotNotificationReferral
method appropriately.

I{Notification Server}

The NotificationClient class handles connections to the
notification server, which acts as a session server
(state updates, message negotiation etc...)

I{Switcboard Server}

The SwitchboardClient handles connections to switchboard
servers which are used to conduct conversations with other users.

There are also two classes (FileSend and FileReceive) used
for file transfers.

Clients handle events in two ways.

  - each client request requiring a response will return a Deferred,
    the callback for same will be fired when the server sends the
    required response
  - Events which are not in response to any client request have
    respective methods which should be overridden and handled in
    an adequate manner

Most client request callbacks require more than one argument,
and since Deferreds can only pass the callback one result,
most of the time the callback argument will be a tuple of
values (documented in the respective request method).
To make reading/writing code easier, callbacks can be defined in
a number of ways to handle this 'cleanly'. One way would be to
define methods like: def callBack(self, (arg1, arg2, arg)): ...
another way would be to do something like:
d.addCallback(lambda result: myCallback(*result)).

If the server sends an error response to a client request,
the errback of the corresponding Deferred will be called,
the argument being the corresponding error code.

B{NOTE}:
Due to the lack of an official spec for MSNP8, extra checking
than may be deemed necessary often takes place considering the
server is never 'wrong'. Thus, if gotBadLine (in any of the 3
main clients) is called, or an MSNProtocolError is raised, it's
probably a good idea to submit a bug report. ;)
Use of this module requires that PyOpenSSL is installed.

TODO
====
- check message hooks with invalid x-msgsinvite messages.
- font handling
- switchboard factory

@author: Sam Jordan
"""

import types, operator, os
from random import randint
from urllib import quote, unquote
from hashlib import md5

from twisted.python import failure, log
from twisted.internet import reactor
from twisted.internet.defer import Deferred, execute
from twisted.internet.protocol import ClientFactory
try:
    from twisted.internet.ssl import ClientContextFactory
except ImportError:
    ClientContextFactory = None
from twisted.protocols.basic import LineReceiver
from twisted.web.http import HTTPClient


MSN_PROTOCOL_VERSION = "MSNP8 CVR0"       # protocol version
MSN_PORT             = 1863               # default dispatch server port
MSN_MAX_MESSAGE      = 1664               # max message length
MSN_CHALLENGE_STR    = "Q1P7W2E4J9R8U3S5" # used for server challenges
MSN_CVR_STR          = "0x0409 win 4.10 i386 MSNMSGR 5.0.0544 MSMSGS" # :(

# auth constants
LOGIN_SUCCESS  = 1
LOGIN_FAILURE  = 2
LOGIN_REDIRECT = 3

# list constants
FORWARD_LIST = 1
ALLOW_LIST   = 2
BLOCK_LIST   = 4
REVERSE_LIST = 8

# phone constants
HOME_PHONE   = "PHH"
WORK_PHONE   = "PHW"
MOBILE_PHONE = "PHM"
HAS_PAGER    = "MOB"

# status constants
STATUS_ONLINE  = 'NLN'
STATUS_OFFLINE = 'FLN'
STATUS_HIDDEN  = 'HDN'
STATUS_IDLE    = 'IDL'
STATUS_AWAY    = 'AWY'
STATUS_BUSY    = 'BSY'
STATUS_BRB     = 'BRB'
STATUS_PHONE   = 'PHN'
STATUS_LUNCH   = 'LUN'

CR = "\r"
LF = "\n"


class SSLRequired(Exception):
    """
    This exception is raised when it is necessary to talk to a passport server
    using SSL, but the necessary SSL dependencies are unavailable.

    @since: 11.0
    """



def checkParamLen(num, expected, cmd, error=None):
    if error == None:
        error = "Invalid Number of Parameters for %s" % cmd
    if num != expected:
        raise MSNProtocolError, error

def _parseHeader(h, v):
    """
    Split a certin number of known
    header values with the format:
    field1=val,field2=val,field3=val into
    a dict mapping fields to values.
    @param h: the header's key
    @param v: the header's value as a string
    """

    if h in ('passporturls','authentication-info','www-authenticate'):
        v = v.replace('Passport1.4','').lstrip()
        fields = {}
        for fieldPair in v.split(','):
            try:
                field,value = fieldPair.split('=',1)
                fields[field.lower()] = value
            except ValueError:
                fields[field.lower()] = ''
        return fields
    else:
        return v

def _parsePrimitiveHost(host):
    # Ho Ho Ho
    h,p = host.replace('https://','').split('/',1)
    p = '/' + p
    return h,p


def _login(userHandle, passwd, nexusServer, cached=0, authData=''):
    """
    This function is used internally and should not ever be called
    directly.

    @raise SSLRequired: If there is no SSL support available.
    """
    if ClientContextFactory is None:
        raise SSLRequired(
            'Connecting to the Passport server requires SSL, but SSL is '
            'unavailable.')

    cb = Deferred()
    def _cb(server, auth):
        loginFac = ClientFactory()
        loginFac.protocol = lambda : PassportLogin(cb, userHandle, passwd, server, auth)
        reactor.connectSSL(_parsePrimitiveHost(server)[0], 443, loginFac, ClientContextFactory())

    if cached:
        _cb(nexusServer, authData)
    else:
        fac = ClientFactory()
        d = Deferred()
        d.addCallbacks(_cb, callbackArgs=(authData,))
        d.addErrback(lambda f: cb.errback(f))
        fac.protocol = lambda : PassportNexus(d, nexusServer)
        reactor.connectSSL(_parsePrimitiveHost(nexusServer)[0], 443, fac, ClientContextFactory())
    return cb


class PassportNexus(HTTPClient):

    """
    Used to obtain the URL of a valid passport
    login HTTPS server.

    This class is used internally and should
    not be instantiated directly -- that is,
    The passport logging in process is handled
    transparently by NotificationClient.
    """

    def __init__(self, deferred, host):
        self.deferred = deferred
        self.host, self.path = _parsePrimitiveHost(host)

    def connectionMade(self):
        HTTPClient.connectionMade(self)
        self.sendCommand('GET', self.path)
        self.sendHeader('Host', self.host)
        self.endHeaders()
        self.headers = {}

    def handleHeader(self, header, value):
        h = header.lower()
        self.headers[h] = _parseHeader(h, value)

    def handleEndHeaders(self):
        if self.connected:
            self.transport.loseConnection()
        if 'passporturls' not in self.headers or 'dalogin' not in self.headers['passporturls']:
            self.deferred.errback(failure.Failure(failure.DefaultException("Invalid Nexus Reply")))
        self.deferred.callback('https://' + self.headers['passporturls']['dalogin'])

    def handleResponse(self, r):
        pass

class PassportLogin(HTTPClient):
    """
    This class is used internally to obtain
    a login ticket from a passport HTTPS
    server -- it should not be used directly.
    """

    _finished = 0

    def __init__(self, deferred, userHandle, passwd, host, authData):
        self.deferred = deferred
        self.userHandle = userHandle
        self.passwd = passwd
        self.authData = authData
        self.host, self.path = _parsePrimitiveHost(host)

    def connectionMade(self):
        self.sendCommand('GET', self.path)
        self.sendHeader('Authorization', 'Passport1.4 OrgVerb=GET,OrgURL=http://messenger.msn.com,' +
                                         'sign-in=%s,pwd=%s,%s' % (quote(self.userHandle), self.passwd,self.authData))
        self.sendHeader('Host', self.host)
        self.endHeaders()
        self.headers = {}

    def handleHeader(self, header, value):
        h = header.lower()
        self.headers[h] = _parseHeader(h, value)

    def handleEndHeaders(self):
        if self._finished:
            return
        self._finished = 1 # I think we need this because of HTTPClient
        if self.connected:
            self.transport.loseConnection()
        authHeader = 'authentication-info'
        _interHeader = 'www-authenticate'
        if _interHeader in self.headers:
            authHeader = _interHeader
        try:
            info = self.headers[authHeader]
            status = info['da-status']
            handler = getattr(self, 'login_%s' % (status,), None)
            if handler:
                handler(info)
            else:
                raise Exception()
        except Exception, e:
            self.deferred.errback(failure.Failure(e))

    def handleResponse(self, r):
        pass

    def login_success(self, info):
        ticket = info['from-pp']
        ticket = ticket[1:len(ticket)-1]
        self.deferred.callback((LOGIN_SUCCESS, ticket))

    def login_failed(self, info):
        self.deferred.callback((LOGIN_FAILURE, unquote(info['cbtxt'])))

    def login_redir(self, info):
        self.deferred.callback((LOGIN_REDIRECT, self.headers['location'], self.authData))


class MSNProtocolError(Exception):
    """
    This Exception is basically used for debugging
    purposes, as the official MSN server should never
    send anything _wrong_ and nobody in their right
    mind would run their B{own} MSN server.
    If it is raised by default command handlers
    (handle_BLAH) the error will be logged.
    """
    pass


class MSNCommandFailed(Exception):
    """
    The server said that the command failed.
    """

    def __init__(self, errorCode):
        self.errorCode = errorCode

    def __str__(self):
        return ("Command failed: %s (error code %d)"
                % (errorCodes[self.errorCode], self.errorCode))


class MSNMessage:
    """
    I am the class used to represent an 'instant' message.

    @ivar userHandle: The user handle (passport) of the sender
                      (this is only used when receiving a message)
    @ivar screenName: The screen name of the sender (this is only used
                      when receiving a message)
    @ivar message: The message
    @ivar headers: The message headers
    @type headers: dict
    @ivar length: The message length (including headers and line endings)
    @ivar ack: This variable is used to tell the server how to respond
               once the message has been sent. If set to MESSAGE_ACK
               (default) the server will respond with an ACK upon receiving
               the message, if set to MESSAGE_NACK the server will respond
               with a NACK upon failure to receive the message.
               If set to MESSAGE_ACK_NONE the server will do nothing.
               This is relevant for the return value of
               SwitchboardClient.sendMessage (which will return
               a Deferred if ack is set to either MESSAGE_ACK or MESSAGE_NACK
               and will fire when the respective ACK or NACK is received).
               If set to MESSAGE_ACK_NONE sendMessage will return None.
    """
    MESSAGE_ACK      = 'A'
    MESSAGE_NACK     = 'N'
    MESSAGE_ACK_NONE = 'U'

    ack = MESSAGE_ACK

    def __init__(self, length=0, userHandle="", screenName="", message=""):
        self.userHandle = userHandle
        self.screenName = screenName
        self.message = message
        self.headers = {'MIME-Version' : '1.0', 'Content-Type' : 'text/plain'}
        self.length = length
        self.readPos = 0

    def _calcMessageLen(self):
        """
        used to calculate the number to send
        as the message length when sending a message.
        """
        return reduce(operator.add, [len(x[0]) + len(x[1]) + 4  for x in self.headers.items()]) + len(self.message) + 2

    def setHeader(self, header, value):
        """ set the desired header """
        self.headers[header] = value

    def getHeader(self, header):
        """
        get the desired header value
        @raise KeyError: if no such header exists.
        """
        return self.headers[header]

    def hasHeader(self, header):
        """ check to see if the desired header exists """
        return header in self.headers

    def getMessage(self):
        """ return the message - not including headers """
        return self.message

    def setMessage(self, message):
        """ set the message text """
        self.message = message

class MSNContact:

    """
    This class represents a contact (user).

    @ivar userHandle: The contact's user handle (passport).
    @ivar screenName: The contact's screen name.
    @ivar groups: A list of all the group IDs which this
                  contact belongs to.
    @ivar lists: An integer representing the sum of all lists
                 that this contact belongs to.
    @ivar status: The contact's status code.
    @type status: str if contact's status is known, None otherwise.

    @ivar homePhone: The contact's home phone number.
    @type homePhone: str if known, otherwise None.
    @ivar workPhone: The contact's work phone number.
    @type workPhone: str if known, otherwise None.
    @ivar mobilePhone: The contact's mobile phone number.
    @type mobilePhone: str if known, otherwise None.
    @ivar hasPager: Whether or not this user has a mobile pager
                    (true=yes, false=no)
    """

    def __init__(self, userHandle="", screenName="", lists=0, groups=[], status=None):
        self.userHandle = userHandle
        self.screenName = screenName
        self.lists = lists
        self.groups = [] # if applicable
        self.status = status # current status

        # phone details
        self.homePhone   = None
        self.workPhone   = None
        self.mobilePhone = None
        self.hasPager    = None

    def setPhone(self, phoneType, value):
        """
        set phone numbers/values for this specific user.
        for phoneType check the *_PHONE constants and HAS_PAGER
        """

        t = phoneType.upper()
        if t == HOME_PHONE:
            self.homePhone = value
        elif t == WORK_PHONE:
            self.workPhone = value
        elif t == MOBILE_PHONE:
            self.mobilePhone = value
        elif t == HAS_PAGER:
            self.hasPager = value
        else:
            raise ValueError, "Invalid Phone Type"

    def addToList(self, listType):
        """
        Update the lists attribute to
        reflect being part of the
        given list.
        """
        self.lists |= listType

    def removeFromList(self, listType):
        """
        Update the lists attribute to
        reflect being removed from the
        given list.
        """
        self.lists ^= listType

class MSNContactList:
    """
    This class represents a basic MSN contact list.

    @ivar contacts: All contacts on my various lists
    @type contacts: dict (mapping user handles to MSNContact objects)
    @ivar version: The current contact list version (used for list syncing)
    @ivar groups: a mapping of group ids to group names
                  (groups can only exist on the forward list)
    @type groups: dict

    B{Note}:
    This is used only for storage and doesn't effect the
    server's contact list.
    """

    def __init__(self):
        self.contacts = {}
        self.version = 0
        self.groups = {}
        self.autoAdd = 0
        self.privacy = 0

    def _getContactsFromList(self, listType):
        """
        Obtain all contacts which belong
        to the given list type.
        """
        return dict([(uH,obj) for uH,obj in self.contacts.items() if obj.lists & listType])

    def addContact(self, contact):
        """
        Add a contact
        """
        self.contacts[contact.userHandle] = contact

    def remContact(self, userHandle):
        """
        Remove a contact
        """
        try:
            del self.contacts[userHandle]
        except KeyError:
            pass

    def getContact(self, userHandle):
        """
        Obtain the MSNContact object
        associated with the given
        userHandle.
        @return: the MSNContact object if
                 the user exists, or None.
        """
        try:
            return self.contacts[userHandle]
        except KeyError:
            return None

    def getBlockedContacts(self):
        """
        Obtain all the contacts on my block list
        """
        return self._getContactsFromList(BLOCK_LIST)

    def getAuthorizedContacts(self):
        """
        Obtain all the contacts on my auth list.
        (These are contacts which I have verified
        can view my state changes).
        """
        return self._getContactsFromList(ALLOW_LIST)

    def getReverseContacts(self):
        """
        Get all contacts on my reverse list.
        (These are contacts which have added me
        to their forward list).
        """
        return self._getContactsFromList(REVERSE_LIST)

    def getContacts(self):
        """
        Get all contacts on my forward list.
        (These are the contacts which I have added
        to my list).
        """
        return self._getContactsFromList(FORWARD_LIST)

    def setGroup(self, id, name):
        """
        Keep a mapping from the given id
        to the given name.
        """
        self.groups[id] = name

    def remGroup(self, id):
        """
        Removed the stored group
        mapping for the given id.
        """
        try:
            del self.groups[id]
        except KeyError:
            pass
        for c in self.contacts:
            if id in c.groups:
                c.groups.remove(id)


class MSNEventBase(LineReceiver):
    """
    This class provides support for handling / dispatching events and is the
    base class of the three main client protocols (DispatchClient,
    NotificationClient, SwitchboardClient)
    """

    def __init__(self):
        self.ids = {} # mapping of ids to Deferreds
        self.currentID = 0
        self.connected = 0
        self.setLineMode()
        self.currentMessage = None

    def connectionLost(self, reason):
        self.ids = {}
        self.connected = 0

    def connectionMade(self):
        self.connected = 1

    def _fireCallback(self, id, *args):
        """
        Fire the callback for the given id
        if one exists and return 1, else return false
        """
        if id in self.ids:
            self.ids[id][0].callback(args)
            del self.ids[id]
            return 1
        return 0

    def _nextTransactionID(self):
        """ return a usable transaction ID """
        self.currentID += 1
        if self.currentID > 1000:
            self.currentID = 1
        return self.currentID

    def _createIDMapping(self, data=None):
        """
        return a unique transaction ID that is mapped internally to a
        deferred .. also store arbitrary data if it is needed
        """
        id = self._nextTransactionID()
        d = Deferred()
        self.ids[id] = (d, data)
        return (id, d)

    def checkMessage(self, message):
        """
        process received messages to check for file invitations and
        typing notifications and other control type messages
        """
        raise NotImplementedError

    def lineReceived(self, line):
        if self.currentMessage:
            self.currentMessage.readPos += len(line+CR+LF)
            if line == "":
                self.setRawMode()
                if self.currentMessage.readPos == self.currentMessage.length:
                    self.rawDataReceived("") # :(
                return
            try:
                header, value = line.split(':')
            except ValueError:
                raise MSNProtocolError, "Invalid Message Header"
            self.currentMessage.setHeader(header, unquote(value).lstrip())
            return
        try:
            cmd, params = line.split(' ', 1)
        except ValueError:
            raise MSNProtocolError, "Invalid Message, %s" % repr(line)

        if len(cmd) != 3:
            raise MSNProtocolError, "Invalid Command, %s" % repr(cmd)
        if cmd.isdigit():
            errorCode = int(cmd)
            id = int(params.split()[0])
            if id in self.ids:
                self.ids[id][0].errback(MSNCommandFailed(errorCode))
                del self.ids[id]
                return
            else:       # we received an error which doesn't map to a sent command
                self.gotError(errorCode)
                return

        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler:
            try:
                handler(params.split())
            except MSNProtocolError, why:
                self.gotBadLine(line, why)
        else:
            self.handle_UNKNOWN(cmd, params.split())

    def rawDataReceived(self, data):
        extra = ""
        self.currentMessage.readPos += len(data)
        diff = self.currentMessage.readPos - self.currentMessage.length
        if diff > 0:
            self.currentMessage.message += data[:-diff]
            extra = data[-diff:]
        elif diff == 0:
            self.currentMessage.message += data
        else:
            self.currentMessage += data
            return
        del self.currentMessage.readPos
        m = self.currentMessage
        self.currentMessage = None
        self.setLineMode(extra)
        if not self.checkMessage(m):
            return
        self.gotMessage(m)

    ### protocol command handlers - no need to override these.

    def handle_MSG(self, params):
        checkParamLen(len(params), 3, 'MSG')
        try:
            messageLen = int(params[2])
        except ValueError:
            raise MSNProtocolError, "Invalid Parameter for MSG length argument"
        self.currentMessage = MSNMessage(length=messageLen, userHandle=params[0], screenName=unquote(params[1]))

    def handle_UNKNOWN(self, cmd, params):
        """ implement me in subclasses if you want to handle unknown events """
        log.msg("Received unknown command (%s), params: %s" % (cmd, params))

    ### callbacks

    def gotMessage(self, message):
        """
        called when we receive a message - override in notification
        and switchboard clients
        """
        raise NotImplementedError

    def gotBadLine(self, line, why):
        """ called when a handler notifies me that this line is broken """
        log.msg('Error in line: %s (%s)' % (line, why))

    def gotError(self, errorCode):
        """
        called when the server sends an error which is not in
        response to a sent command (ie. it has no matching transaction ID)
        """
        log.msg('Error %s' % (errorCodes[errorCode]))



class DispatchClient(MSNEventBase):
    """
    This class provides support for clients connecting to the dispatch server
    @ivar userHandle: your user handle (passport) needed before connecting.
    """

    # eventually this may become an attribute of the
    # factory.
    userHandle = ""

    def connectionMade(self):
        MSNEventBase.connectionMade(self)
        self.sendLine('VER %s %s' % (self._nextTransactionID(), MSN_PROTOCOL_VERSION))

    ### protocol command handlers ( there is no need to override these )

    def handle_VER(self, params):
        id = self._nextTransactionID()
        self.sendLine("CVR %s %s %s" % (id, MSN_CVR_STR, self.userHandle))

    def handle_CVR(self, params):
        self.sendLine("USR %s TWN I %s" % (self._nextTransactionID(), self.userHandle))

    def handle_XFR(self, params):
        if len(params) < 4:
            raise MSNProtocolError, "Invalid number of parameters for XFR"
        id, refType, addr = params[:3]
        # was addr a host:port pair?
        try:
            host, port = addr.split(':')
        except ValueError:
            host = addr
            port = MSN_PORT
        if refType == "NS":
            self.gotNotificationReferral(host, int(port))

    ### callbacks

    def gotNotificationReferral(self, host, port):
        """
        called when we get a referral to the notification server.

        @param host: the notification server's hostname
        @param port: the port to connect to
        """
        pass


class NotificationClient(MSNEventBase):
    """
    This class provides support for clients connecting
    to the notification server.
    """

    factory = None # sssh pychecker

    def __init__(self, currentID=0):
        MSNEventBase.__init__(self)
        self.currentID = currentID
        self._state = ['DISCONNECTED', {}]

    def _setState(self, state):
        self._state[0] = state

    def _getState(self):
        return self._state[0]

    def _getStateData(self, key):
        return self._state[1][key]

    def _setStateData(self, key, value):
        self._state[1][key] = value

    def _remStateData(self, *args):
        for key in args:
            del self._state[1][key]

    def connectionMade(self):
        MSNEventBase.connectionMade(self)
        self._setState('CONNECTED')
        self.sendLine("VER %s %s" % (self._nextTransactionID(), MSN_PROTOCOL_VERSION))

    def connectionLost(self, reason):
        self._setState('DISCONNECTED')
        self._state[1] = {}
        MSNEventBase.connectionLost(self, reason)

    def checkMessage(self, message):
        """ hook used for detecting specific notification messages """
        cTypes = [s.lstrip() for s in message.getHeader('Content-Type').split(';')]
        if 'text/x-msmsgsprofile' in cTypes:
            self.gotProfile(message)
            return 0
        return 1

    ### protocol command handlers - no need to override these

    def handle_VER(self, params):
        id = self._nextTransactionID()
        self.sendLine("CVR %s %s %s" % (id, MSN_CVR_STR, self.factory.userHandle))

    def handle_CVR(self, params):
        self.sendLine("USR %s TWN I %s" % (self._nextTransactionID(), self.factory.userHandle))

    def handle_USR(self, params):
        if len(params) != 4 and len(params) != 6:
            raise MSNProtocolError, "Invalid Number of Parameters for USR"

        mechanism = params[1]
        if mechanism == "OK":
            self.loggedIn(params[2], unquote(params[3]), int(params[4]))
        elif params[2].upper() == "S":
            # we need to obtain auth from a passport server
            f = self.factory
            d = execute(
                _login, f.userHandle, f.password, f.passportServer,
                authData=params[3])
            d.addCallback(self._passportLogin)
            d.addErrback(self._passportError)

    def _passportLogin(self, result):
        if result[0] == LOGIN_REDIRECT:
            d = _login(self.factory.userHandle, self.factory.password,
                       result[1], cached=1, authData=result[2])
            d.addCallback(self._passportLogin)
            d.addErrback(self._passportError)
        elif result[0] == LOGIN_SUCCESS:
            self.sendLine("USR %s TWN S %s" % (self._nextTransactionID(), result[1]))
        elif result[0] == LOGIN_FAILURE:
            self.loginFailure(result[1])


    def _passportError(self, failure):
        """
        Handle a problem logging in via the Passport server, passing on the
        error as a string message to the C{loginFailure} callback.
        """
        if failure.check(SSLRequired):
            failure = failure.getErrorMessage()
        self.loginFailure("Exception while authenticating: %s" % failure)


    def handle_CHG(self, params):
        checkParamLen(len(params), 3, 'CHG')
        id = int(params[0])
        if not self._fireCallback(id, params[1]):
            self.statusChanged(params[1])

    def handle_ILN(self, params):
        checkParamLen(len(params), 5, 'ILN')
        self.gotContactStatus(params[1], params[2], unquote(params[3]))

    def handle_CHL(self, params):
        checkParamLen(len(params), 2, 'CHL')
        self.sendLine("QRY %s msmsgs@msnmsgr.com 32" % self._nextTransactionID())
        self.transport.write(md5(params[1] + MSN_CHALLENGE_STR).hexdigest())

    def handle_QRY(self, params):
        pass

    def handle_NLN(self, params):
        checkParamLen(len(params), 4, 'NLN')
        self.contactStatusChanged(params[0], params[1], unquote(params[2]))

    def handle_FLN(self, params):
        checkParamLen(len(params), 1, 'FLN')
        self.contactOffline(params[0])

    def handle_LST(self, params):
        # support no longer exists for manually
        # requesting lists - why do I feel cleaner now?
        if self._getState() != 'SYNC':
            return
        contact = MSNContact(userHandle=params[0], screenName=unquote(params[1]),
                             lists=int(params[2]))
        if contact.lists & FORWARD_LIST:
            contact.groups.extend(map(int, params[3].split(',')))
        self._getStateData('list').addContact(contact)
        self._setStateData('last_contact', contact)
        sofar = self._getStateData('lst_sofar') + 1
        if sofar == self._getStateData('lst_reply'):
            # this is the best place to determine that
            # a syn really has finished - msn _may_ send
            # BPR information for the last contact
            # which is unfortunate because it means
            # that the real end of a syn is non-deterministic.
            # to handle this we'll keep 'last_contact' hanging
            # around in the state data and update it if we need
            # to later.
            self._setState('SESSION')
            contacts = self._getStateData('list')
            phone = self._getStateData('phone')
            id = self._getStateData('synid')
            self._remStateData('lst_reply', 'lsg_reply', 'lst_sofar', 'phone', 'synid', 'list')
            self._fireCallback(id, contacts, phone)
        else:
            self._setStateData('lst_sofar',sofar)

    def handle_BLP(self, params):
        # check to see if this is in response to a SYN
        if self._getState() == 'SYNC':
            self._getStateData('list').privacy = listCodeToID[params[0].lower()]
        else:
            id = int(params[0])
            self._fireCallback(id, int(params[1]), listCodeToID[params[2].lower()])

    def handle_GTC(self, params):
        # check to see if this is in response to a SYN
        if self._getState() == 'SYNC':
            if params[0].lower() == "a":
                self._getStateData('list').autoAdd = 0
            elif params[0].lower() == "n":
                self._getStateData('list').autoAdd = 1
            else:
                raise MSNProtocolError, "Invalid Parameter for GTC" # debug
        else:
            id = int(params[0])
            if params[1].lower() == "a":
                self._fireCallback(id, 0)
            elif params[1].lower() == "n":
                self._fireCallback(id, 1)
            else:
                raise MSNProtocolError, "Invalid Parameter for GTC" # debug

    def handle_SYN(self, params):
        id = int(params[0])
        if len(params) == 2:
            self._setState('SESSION')
            self._fireCallback(id, None, None)
        else:
            contacts = MSNContactList()
            contacts.version = int(params[1])
            self._setStateData('list', contacts)
            self._setStateData('lst_reply', int(params[2]))
            self._setStateData('lsg_reply', int(params[3]))
            self._setStateData('lst_sofar', 0)
            self._setStateData('phone', [])

    def handle_LSG(self, params):
        if self._getState() == 'SYNC':
            self._getStateData('list').groups[int(params[0])] = unquote(params[1])

        # Please see the comment above the requestListGroups / requestList methods
        # regarding support for this
        #
        #else:
        #    self._getStateData('groups').append((int(params[4]), unquote(params[5])))
        #    if params[3] == params[4]: # this was the last group
        #        self._fireCallback(int(params[0]), self._getStateData('groups'), int(params[1]))
        #        self._remStateData('groups')

    def handle_PRP(self, params):
        if self._getState() == 'SYNC':
            self._getStateData('phone').append((params[0], unquote(params[1])))
        else:
            self._fireCallback(int(params[0]), int(params[1]), unquote(params[3]))

    def handle_BPR(self, params):
        numParams = len(params)
        if numParams == 2: # part of a syn
            self._getStateData('last_contact').setPhone(params[0], unquote(params[1]))
        elif numParams == 4:
            self.gotPhoneNumber(int(params[0]), params[1], params[2], unquote(params[3]))

    def handle_ADG(self, params):
        checkParamLen(len(params), 5, 'ADG')
        id = int(params[0])
        if not self._fireCallback(id, int(params[1]), unquote(params[2]), int(params[3])):
            raise MSNProtocolError, "ADG response does not match up to a request" # debug

    def handle_RMG(self, params):
        checkParamLen(len(params), 3, 'RMG')
        id = int(params[0])
        if not self._fireCallback(id, int(params[1]), int(params[2])):
            raise MSNProtocolError, "RMG response does not match up to a request" # debug

    def handle_REG(self, params):
        checkParamLen(len(params), 5, 'REG')
        id = int(params[0])
        if not self._fireCallback(id, int(params[1]), int(params[2]), unquote(params[3])):
            raise MSNProtocolError, "REG response does not match up to a request" # debug

    def handle_ADD(self, params):
        numParams = len(params)
        if numParams < 5 or params[1].upper() not in ('AL','BL','RL','FL'):
            raise MSNProtocolError, "Invalid Parameters for ADD" # debug
        id = int(params[0])
        listType = params[1].lower()
        listVer = int(params[2])
        userHandle = params[3]
        groupID = None
        if numParams == 6: # they sent a group id
            if params[1].upper() != "FL":
                raise MSNProtocolError, "Only forward list can contain groups" # debug
            groupID = int(params[5])
        if not self._fireCallback(id, listCodeToID[listType], userHandle, listVer, groupID):
            self.userAddedMe(userHandle, unquote(params[4]), listVer)

    def handle_REM(self, params):
        numParams = len(params)
        if numParams < 4 or params[1].upper() not in ('AL','BL','FL','RL'):
            raise MSNProtocolError, "Invalid Parameters for REM" # debug
        id = int(params[0])
        listType = params[1].lower()
        listVer = int(params[2])
        userHandle = params[3]
        groupID = None
        if numParams == 5:
            if params[1] != "FL":
                raise MSNProtocolError, "Only forward list can contain groups" # debug
            groupID = int(params[4])
        if not self._fireCallback(id, listCodeToID[listType], userHandle, listVer, groupID):
            if listType.upper() == "RL":
                self.userRemovedMe(userHandle, listVer)

    def handle_REA(self, params):
        checkParamLen(len(params), 4, 'REA')
        id = int(params[0])
        self._fireCallback(id, int(params[1]), unquote(params[3]))

    def handle_XFR(self, params):
        checkParamLen(len(params), 5, 'XFR')
        id = int(params[0])
        # check to see if they sent a host/port pair
        try:
            host, port = params[2].split(':')
        except ValueError:
            host = params[2]
            port = MSN_PORT

        if not self._fireCallback(id, host, int(port), params[4]):
            raise MSNProtocolError, "Got XFR (referral) that I didn't ask for .. should this happen?" # debug

    def handle_RNG(self, params):
        checkParamLen(len(params), 6, 'RNG')
        # check for host:port pair
        try:
            host, port = params[1].split(":")
            port = int(port)
        except ValueError:
            host = params[1]
            port = MSN_PORT
        self.gotSwitchboardInvitation(int(params[0]), host, port, params[3], params[4],
                                      unquote(params[5]))

    def handle_OUT(self, params):
        checkParamLen(len(params), 1, 'OUT')
        if params[0] == "OTH":
            self.multipleLogin()
        elif params[0] == "SSD":
            self.serverGoingDown()
        else:
            raise MSNProtocolError, "Invalid Parameters received for OUT" # debug

    # callbacks

    def loggedIn(self, userHandle, screenName, verified):
        """
        Called when the client has logged in.
        The default behaviour of this method is to
        update the factory with our screenName and
        to sync the contact list (factory.contacts).
        When this is complete self.listSynchronized
        will be called.

        @param userHandle: our userHandle
        @param screenName: our screenName
        @param verified: 1 if our passport has been (verified), 0 if not.
                         (i'm not sure of the significance of this)
        @type verified: int
        """
        self.factory.screenName = screenName
        if not self.factory.contacts:
            listVersion = 0
        else:
            listVersion = self.factory.contacts.version
        self.syncList(listVersion).addCallback(self.listSynchronized)


    def loginFailure(self, message):
        """
        Called when the client fails to login.

        @param message: a message indicating the problem that was encountered
        """


    def gotProfile(self, message):
        """
        Called after logging in when the server sends an initial
        message with MSN/passport specific profile information
        such as country, number of kids, etc.
        Check the message headers for the specific values.

        @param message: The profile message
        """
        pass

    def listSynchronized(self, *args):
        """
        Lists are now synchronized by default upon logging in, this
        method is called after the synchronization has finished
        and the factory now has the up-to-date contacts.
        """
        pass

    def statusChanged(self, statusCode):
        """
        Called when our status changes and it isn't in response to
        a client command. By default we will update the status
        attribute of the factory.

        @param statusCode: 3-letter status code
        """
        self.factory.status = statusCode

    def gotContactStatus(self, statusCode, userHandle, screenName):
        """
        Called after loggin in when the server sends status of online contacts.
        By default we will update the status attribute of the contact stored
        on the factory.

        @param statusCode: 3-letter status code
        @param userHandle: the contact's user handle (passport)
        @param screenName: the contact's screen name
        """
        self.factory.contacts.getContact(userHandle).status = statusCode

    def contactStatusChanged(self, statusCode, userHandle, screenName):
        """
        Called when we're notified that a contact's status has changed.
        By default we will update the status attribute of the contact
        stored on the factory.

        @param statusCode: 3-letter status code
        @param userHandle: the contact's user handle (passport)
        @param screenName: the contact's screen name
        """
        self.factory.contacts.getContact(userHandle).status = statusCode

    def contactOffline(self, userHandle):
        """
        Called when a contact goes offline. By default this method
        will update the status attribute of the contact stored
        on the factory.

        @param userHandle: the contact's user handle
        """
        self.factory.contacts.getContact(userHandle).status = STATUS_OFFLINE

    def gotPhoneNumber(self, listVersion, userHandle, phoneType, number):
        """
        Called when the server sends us phone details about
        a specific user (for example after a user is added
        the server will send their status, phone details etc.
        By default we will update the list version for the
        factory's contact list and update the phone details
        for the specific user.

        @param listVersion: the new list version
        @param userHandle: the contact's user handle (passport)
        @param phoneType: the specific phoneType
                          (*_PHONE constants or HAS_PAGER)
        @param number: the value/phone number.
        """
        self.factory.contacts.version = listVersion
        self.factory.contacts.getContact(userHandle).setPhone(phoneType, number)

    def userAddedMe(self, userHandle, screenName, listVersion):
        """
        Called when a user adds me to their list. (ie. they have been added to
        the reverse list. By default this method will update the version of
        the factory's contact list -- that is, if the contact already exists
        it will update the associated lists attribute, otherwise it will create
        a new MSNContact object and store it.

        @param userHandle: the userHandle of the user
        @param screenName: the screen name of the user
        @param listVersion: the new list version
        @type listVersion: int
        """
        self.factory.contacts.version = listVersion
        c = self.factory.contacts.getContact(userHandle)
        if not c:
            c = MSNContact(userHandle=userHandle, screenName=screenName)
            self.factory.contacts.addContact(c)
        c.addToList(REVERSE_LIST)

    def userRemovedMe(self, userHandle, listVersion):
        """
        Called when a user removes us from their contact list
        (they are no longer on our reverseContacts list.
        By default this method will update the version of
        the factory's contact list -- that is, the user will
        be removed from the reverse list and if they are no longer
        part of any lists they will be removed from the contact
        list entirely.

        @param userHandle: the contact's user handle (passport)
        @param listVersion: the new list version
        """
        self.factory.contacts.version = listVersion
        c = self.factory.contacts.getContact(userHandle)
        c.removeFromList(REVERSE_LIST)
        if c.lists == 0:
            self.factory.contacts.remContact(c.userHandle)

    def gotSwitchboardInvitation(self, sessionID, host, port,
                                 key, userHandle, screenName):
        """
        Called when we get an invitation to a switchboard server.
        This happens when a user requests a chat session with us.

        @param sessionID: session ID number, must be remembered for logging in
        @param host: the hostname of the switchboard server
        @param port: the port to connect to
        @param key: used for authorization when connecting
        @param userHandle: the user handle of the person who invited us
        @param screenName: the screen name of the person who invited us
        """
        pass

    def multipleLogin(self):
        """
        Called when the server says there has been another login
        under our account, the server should disconnect us right away.
        """
        pass

    def serverGoingDown(self):
        """
        Called when the server has notified us that it is going down for
        maintenance.
        """
        pass

    # api calls

    def changeStatus(self, status):
        """
        Change my current status. This method will add
        a default callback to the returned Deferred
        which will update the status attribute of the
        factory.

        @param status: 3-letter status code (as defined by
                       the STATUS_* constants)
        @return: A Deferred, the callback of which will be
                 fired when the server confirms the change
                 of status.  The callback argument will be
                 a tuple with the new status code as the
                 only element.
        """

        id, d = self._createIDMapping()
        self.sendLine("CHG %s %s" % (id, status))
        def _cb(r):
            self.factory.status = r[0]
            return r
        return d.addCallback(_cb)

    # I am no longer supporting the process of manually requesting
    # lists or list groups -- as far as I can see this has no use
    # if lists are synchronized and updated correctly, which they
    # should be. If someone has a specific justified need for this
    # then please contact me and i'll re-enable/fix support for it.

    #def requestList(self, listType):
    #    """
    #    request the desired list type
    #
    #    @param listType: (as defined by the *_LIST constants)
    #    @return: A Deferred, the callback of which will be
    #             fired when the list has been retrieved.
    #             The callback argument will be a tuple with
    #             the only element being a list of MSNContact
    #             objects.
    #    """
    #    # this doesn't need to ever be used if syncing of the lists takes place
    #    # i.e. please don't use it!
    #    warnings.warn("Please do not use this method - use the list syncing process instead")
    #    id, d = self._createIDMapping()
    #    self.sendLine("LST %s %s" % (id, listIDToCode[listType].upper()))
    #    self._setStateData('list',[])
    #    return d

    def setPrivacyMode(self, privLevel):
        """
        Set my privacy mode on the server.

        B{Note}:
        This only keeps the current privacy setting on
        the server for later retrieval, it does not
        effect the way the server works at all.

        @param privLevel: This parameter can be true, in which
                          case the server will keep the state as
                          'al' which the official client interprets
                          as -> allow messages from only users on
                          the allow list.  Alternatively it can be
                          false, in which case the server will keep
                          the state as 'bl' which the official client
                          interprets as -> allow messages from all
                          users except those on the block list.

        @return: A Deferred, the callback of which will be fired when
                 the server replies with the new privacy setting.
                 The callback argument will be a tuple, the 2 elements
                 of which being the list version and either 'al'
                 or 'bl' (the new privacy setting).
        """

        id, d = self._createIDMapping()
        if privLevel:
            self.sendLine("BLP %s AL" % id)
        else:
            self.sendLine("BLP %s BL" % id)
        return d

    def syncList(self, version):
        """
        Used for keeping an up-to-date contact list.
        A callback is added to the returned Deferred
        that updates the contact list on the factory
        and also sets my state to STATUS_ONLINE.

        B{Note}:
        This is called automatically upon signing
        in using the version attribute of
        factory.contacts, so you may want to persist
        this object accordingly. Because of this there
        is no real need to ever call this method
        directly.

        @param version: The current known list version

        @return: A Deferred, the callback of which will be
                 fired when the server sends an adequate reply.
                 The callback argument will be a tuple with two
                 elements, the new list (MSNContactList) and
                 your current state (a dictionary).  If the version
                 you sent _was_ the latest list version, both elements
                 will be None. To just request the list send a version of 0.
        """

        self._setState('SYNC')
        id, d = self._createIDMapping(data=str(version))
        self._setStateData('synid',id)
        self.sendLine("SYN %s %s" % (id, version))
        def _cb(r):
            self.changeStatus(STATUS_ONLINE)
            if r[0] is not None:
                self.factory.contacts = r[0]
            return r
        return d.addCallback(_cb)


    # I am no longer supporting the process of manually requesting
    # lists or list groups -- as far as I can see this has no use
    # if lists are synchronized and updated correctly, which they
    # should be. If someone has a specific justified need for this
    # then please contact me and i'll re-enable/fix support for it.

    #def requestListGroups(self):
    #    """
    #    Request (forward) list groups.
    #
    #    @return: A Deferred, the callback for which will be called
    #             when the server responds with the list groups.
    #             The callback argument will be a tuple with two elements,
    #             a dictionary mapping group IDs to group names and the
    #             current list version.
    #    """
    #
    #    # this doesn't need to be used if syncing of the lists takes place (which it SHOULD!)
    #    # i.e. please don't use it!
    #    warnings.warn("Please do not use this method - use the list syncing process instead")
    #    id, d = self._createIDMapping()
    #    self.sendLine("LSG %s" % id)
    #    self._setStateData('groups',{})
    #    return d

    def setPhoneDetails(self, phoneType, value):
        """
        Set/change my phone numbers stored on the server.

        @param phoneType: phoneType can be one of the following
                          constants - HOME_PHONE, WORK_PHONE,
                          MOBILE_PHONE, HAS_PAGER.
                          These are pretty self-explanatory, except
                          maybe HAS_PAGER which refers to whether or
                          not you have a pager.
        @param value: for all of the *_PHONE constants the value is a
                      phone number (str), for HAS_PAGER accepted values
                      are 'Y' (for yes) and 'N' (for no).

        @return: A Deferred, the callback for which will be fired when
                 the server confirms the change has been made. The
                 callback argument will be a tuple with 2 elements, the
                 first being the new list version (int) and the second
                 being the new phone number value (str).
        """
        # XXX: Add a default callback which updates
        # factory.contacts.version and the relevant phone
        # number
        id, d = self._createIDMapping()
        self.sendLine("PRP %s %s %s" % (id, phoneType, quote(value)))
        return d

    def addListGroup(self, name):
        """
        Used to create a new list group.
        A default callback is added to the
        returned Deferred which updates the
        contacts attribute of the factory.

        @param name: The desired name of the new group.

        @return: A Deferred, the callbacck for which will be called
                 when the server clarifies that the new group has been
                 created.  The callback argument will be a tuple with 3
                 elements: the new list version (int), the new group name
                 (str) and the new group ID (int).
        """

        id, d = self._createIDMapping()
        self.sendLine("ADG %s %s 0" % (id, quote(name)))
        def _cb(r):
            self.factory.contacts.version = r[0]
            self.factory.contacts.setGroup(r[1], r[2])
            return r
        return d.addCallback(_cb)

    def remListGroup(self, groupID):
        """
        Used to remove a list group.
        A default callback is added to the
        returned Deferred which updates the
        contacts attribute of the factory.

        @param groupID: the ID of the desired group to be removed.

        @return: A Deferred, the callback for which will be called when
                 the server clarifies the deletion of the group.
                 The callback argument will be a tuple with 2 elements:
                 the new list version (int) and the group ID (int) of
                 the removed group.
        """

        id, d = self._createIDMapping()
        self.sendLine("RMG %s %s" % (id, groupID))
        def _cb(r):
            self.factory.contacts.version = r[0]
            self.factory.contacts.remGroup(r[1])
            return r
        return d.addCallback(_cb)

    def renameListGroup(self, groupID, newName):
        """
        Used to rename an existing list group.
        A default callback is added to the returned
        Deferred which updates the contacts attribute
        of the factory.

        @param groupID: the ID of the desired group to rename.
        @param newName: the desired new name for the group.

        @return: A Deferred, the callback for which will be called
                 when the server clarifies the renaming.
                 The callback argument will be a tuple of 3 elements,
                 the new list version (int), the group id (int) and
                 the new group name (str).
        """

        id, d = self._createIDMapping()
        self.sendLine("REG %s %s %s 0" % (id, groupID, quote(newName)))
        def _cb(r):
            self.factory.contacts.version = r[0]
            self.factory.contacts.setGroup(r[1], r[2])
            return r
        return d.addCallback(_cb)

    def addContact(self, listType, userHandle, groupID=0):
        """
        Used to add a contact to the desired list.
        A default callback is added to the returned
        Deferred which updates the contacts attribute of
        the factory with the new contact information.
        If you are adding a contact to the forward list
        and you want to associate this contact with multiple
        groups then you will need to call this method for each
        group you would like to add them to, changing the groupID
        parameter. The default callback will take care of updating
        the group information on the factory's contact list.

        @param listType: (as defined by the *_LIST constants)
        @param userHandle: the user handle (passport) of the contact
                           that is being added
        @param groupID: the group ID for which to associate this contact
                        with. (default 0 - default group). Groups are only
                        valid for FORWARD_LIST.

        @return: A Deferred, the callback for which will be called when
                 the server has clarified that the user has been added.
                 The callback argument will be a tuple with 4 elements:
                 the list type, the contact's user handle, the new list
                 version, and the group id (if relevant, otherwise it
                 will be None)
        """

        id, d = self._createIDMapping()
        listType = listIDToCode[listType].upper()
        if listType == "FL":
            self.sendLine("ADD %s FL %s %s %s" % (id, userHandle, userHandle, groupID))
        else:
            self.sendLine("ADD %s %s %s %s" % (id, listType, userHandle, userHandle))

        def _cb(r):
            self.factory.contacts.version = r[2]
            c = self.factory.contacts.getContact(r[1])
            if not c:
                c = MSNContact(userHandle=r[1])
            if r[3]:
                c.groups.append(r[3])
            c.addToList(r[0])
            return r
        return d.addCallback(_cb)

    def remContact(self, listType, userHandle, groupID=0):
        """
        Used to remove a contact from the desired list.
        A default callback is added to the returned deferred
        which updates the contacts attribute of the factory
        to reflect the new contact information. If you are
        removing from the forward list then you will need to
        supply a groupID, if the contact is in more than one
        group then they will only be removed from this group
        and not the entire forward list, but if this is their
        only group they will be removed from the whole list.

        @param listType: (as defined by the *_LIST constants)
        @param userHandle: the user handle (passport) of the
                           contact being removed
        @param groupID: the ID of the group to which this contact
                        belongs (only relevant for FORWARD_LIST,
                        default is 0)

        @return: A Deferred, the callback for which will be called when
                 the server has clarified that the user has been removed.
                 The callback argument will be a tuple of 4 elements:
                 the list type, the contact's user handle, the new list
                 version, and the group id (if relevant, otherwise it will
                 be None)
        """

        id, d = self._createIDMapping()
        listType = listIDToCode[listType].upper()
        if listType == "FL":
            self.sendLine("REM %s FL %s %s" % (id, userHandle, groupID))
        else:
            self.sendLine("REM %s %s %s" % (id, listType, userHandle))

        def _cb(r):
            l = self.factory.contacts
            l.version = r[2]
            c = l.getContact(r[1])
            group = r[3]
            shouldRemove = 1
            if group: # they may not have been removed from the list
                c.groups.remove(group)
                if c.groups:
                    shouldRemove = 0
            if shouldRemove:
                c.removeFromList(r[0])
                if c.lists == 0:
                    l.remContact(c.userHandle)
            return r
        return d.addCallback(_cb)

    def changeScreenName(self, newName):
        """
        Used to change your current screen name.
        A default callback is added to the returned
        Deferred which updates the screenName attribute
        of the factory and also updates the contact list
        version.

        @param newName: the new screen name

        @return: A Deferred, the callback for which will be called
                 when the server sends an adequate reply.
                 The callback argument will be a tuple of 2 elements:
                 the new list version and the new screen name.
        """

        id, d = self._createIDMapping()
        self.sendLine("REA %s %s %s" % (id, self.factory.userHandle, quote(newName)))
        def _cb(r):
            self.factory.contacts.version = r[0]
            self.factory.screenName = r[1]
            return r
        return d.addCallback(_cb)

    def requestSwitchboardServer(self):
        """
        Used to request a switchboard server to use for conversations.

        @return: A Deferred, the callback for which will be called when
                 the server responds with the switchboard information.
                 The callback argument will be a tuple with 3 elements:
                 the host of the switchboard server, the port and a key
                 used for logging in.
        """

        id, d = self._createIDMapping()
        self.sendLine("XFR %s SB" % id)
        return d

    def logOut(self):
        """
        Used to log out of the notification server.
        After running the method the server is expected
        to close the connection.
        """

        self.sendLine("OUT")

class NotificationFactory(ClientFactory):
    """
    Factory for the NotificationClient protocol.
    This is basically responsible for keeping
    the state of the client and thus should be used
    in a 1:1 situation with clients.

    @ivar contacts: An MSNContactList instance reflecting
                    the current contact list -- this is
                    generally kept up to date by the default
                    command handlers.
    @ivar userHandle: The client's userHandle, this is expected
                      to be set by the client and is used by the
                      protocol (for logging in etc).
    @ivar screenName: The client's current screen-name -- this is
                      generally kept up to date by the default
                      command handlers.
    @ivar password: The client's password -- this is (obviously)
                    expected to be set by the client.
    @ivar passportServer: This must point to an msn passport server
                          (the whole URL is required)
    @ivar status: The status of the client -- this is generally kept
                  up to date by the default command handlers
    """

    contacts = None
    userHandle = ''
    screenName = ''
    password = ''
    passportServer = 'https://nexus.passport.com/rdr/pprdr.asp'
    status = 'FLN'
    protocol = NotificationClient


# XXX: A lot of the state currently kept in
# instances of SwitchboardClient is likely to
# be moved into a factory at some stage in the
# future

class SwitchboardClient(MSNEventBase):
    """
    This class provides support for clients connecting to a switchboard server.

    Switchboard servers are used for conversations with other people
    on the MSN network. This means that the number of conversations at
    any given time will be directly proportional to the number of
    connections to varioius switchboard servers.

    MSN makes no distinction between single and group conversations,
    so any number of users may be invited to join a specific conversation
    taking place on a switchboard server.

    @ivar key: authorization key, obtained when receiving
               invitation / requesting switchboard server.
    @ivar userHandle: your user handle (passport)
    @ivar sessionID: unique session ID, used if you are replying
                     to a switchboard invitation
    @ivar reply: set this to 1 in connectionMade or before to signifiy
                 that you are replying to a switchboard invitation.
    """

    key = 0
    userHandle = ""
    sessionID = ""
    reply = 0

    _iCookie = 0

    def __init__(self):
        MSNEventBase.__init__(self)
        self.pendingUsers = {}
        self.cookies = {'iCookies' : {}, 'external' : {}} # will maybe be moved to a factory in the future

    def connectionMade(self):
        MSNEventBase.connectionMade(self)
        print 'sending initial stuff'
        self._sendInit()

    def connectionLost(self, reason):
        self.cookies['iCookies'] = {}
        self.cookies['external'] = {}
        MSNEventBase.connectionLost(self, reason)

    def _sendInit(self):
        """
        send initial data based on whether we are replying to an invitation
        or starting one.
        """
        id = self._nextTransactionID()
        if not self.reply:
            self.sendLine("USR %s %s %s" % (id, self.userHandle, self.key))
        else:
            self.sendLine("ANS %s %s %s %s" % (id, self.userHandle, self.key, self.sessionID))

    def _newInvitationCookie(self):
        self._iCookie += 1
        if self._iCookie > 1000:
            self._iCookie = 1
        return self._iCookie

    def _checkTyping(self, message, cTypes):
        """ helper method for checkMessage """
        if 'text/x-msmsgscontrol' in cTypes and message.hasHeader('TypingUser'):
            self.userTyping(message)
            return 1

    def _checkFileInvitation(self, message, info):
        """ helper method for checkMessage """
        guid = info.get('Application-GUID', '').lower()
        name = info.get('Application-Name', '').lower()

        # Both fields are required, but we'll let some lazy clients get away
        # with only sending a name, if it is easy for us to recognize the
        # name (the name is localized, so this check might fail for lazy,
        # non-english clients, but I'm not about to include "file transfer"
        # in 80 different languages here).

        if name != "file transfer" and guid != classNameToGUID["file transfer"]:
            return 0
        try:
            cookie = int(info['Invitation-Cookie'])
            fileName = info['Application-File']
            fileSize = int(info['Application-FileSize'])
        except KeyError:
            log.msg('Received munged file transfer request ... ignoring.')
            return 0
        self.gotSendRequest(fileName, fileSize, cookie, message)
        return 1

    def _checkFileResponse(self, message, info):
        """ helper method for checkMessage """
        try:
            cmd = info['Invitation-Command'].upper()
            cookie = int(info['Invitation-Cookie'])
        except KeyError:
            return 0
        accept = (cmd == 'ACCEPT') and 1 or 0
        requested = self.cookies['iCookies'].get(cookie)
        if not requested:
            return 1
        requested[0].callback((accept, cookie, info))
        del self.cookies['iCookies'][cookie]
        return 1

    def _checkFileInfo(self, message, info):
        """ helper method for checkMessage """
        try:
            ip = info['IP-Address']
            iCookie = int(info['Invitation-Cookie'])
            aCookie = int(info['AuthCookie'])
            cmd = info['Invitation-Command'].upper()
            port = int(info['Port'])
        except KeyError:
            return 0
        accept = (cmd == 'ACCEPT') and 1 or 0
        requested = self.cookies['external'].get(iCookie)
        if not requested:
            return 1 # we didn't ask for this
        requested[0].callback((accept, ip, port, aCookie, info))
        del self.cookies['external'][iCookie]
        return 1

    def checkMessage(self, message):
        """
        hook for detecting any notification type messages
        (e.g. file transfer)
        """
        cTypes = [s.lstrip() for s in message.getHeader('Content-Type').split(';')]
        if self._checkTyping(message, cTypes):
            return 0
        if 'text/x-msmsgsinvite' in cTypes:
            # header like info is sent as part of the message body.
            info = {}
            for line in message.message.split('\r\n'):
                try:
                    key, val = line.split(':')
                    info[key] = val.lstrip()
                except ValueError:
                    continue
            if self._checkFileInvitation(message, info) or self._checkFileInfo(message, info) or self._checkFileResponse(message, info):
                return 0
        elif 'text/x-clientcaps' in cTypes:
            # do something with capabilities
            return 0
        return 1

    # negotiation
    def handle_USR(self, params):
        checkParamLen(len(params), 4, 'USR')
        if params[1] == "OK":
            self.loggedIn()

    # invite a user
    def handle_CAL(self, params):
        checkParamLen(len(params), 3, 'CAL')
        id = int(params[0])
        if params[1].upper() == "RINGING":
            self._fireCallback(id, int(params[2])) # session ID as parameter

    # user joined
    def handle_JOI(self, params):
        checkParamLen(len(params), 2, 'JOI')
        self.userJoined(params[0], unquote(params[1]))

    # users participating in the current chat
    def handle_IRO(self, params):
        checkParamLen(len(params), 5, 'IRO')
        self.pendingUsers[params[3]] = unquote(params[4])
        if params[1] == params[2]:
            self.gotChattingUsers(self.pendingUsers)
            self.pendingUsers = {}

    # finished listing users
    def handle_ANS(self, params):
        checkParamLen(len(params), 2, 'ANS')
        if params[1] == "OK":
            self.loggedIn()

    def handle_ACK(self, params):
        checkParamLen(len(params), 1, 'ACK')
        self._fireCallback(int(params[0]), None)

    def handle_NAK(self, params):
        checkParamLen(len(params), 1, 'NAK')
        self._fireCallback(int(params[0]), None)

    def handle_BYE(self, params):
        #checkParamLen(len(params), 1, 'BYE') # i've seen more than 1 param passed to this
        self.userLeft(params[0])

    # callbacks

    def loggedIn(self):
        """
        called when all login details have been negotiated.
        Messages can now be sent, or new users invited.
        """
        pass

    def gotChattingUsers(self, users):
        """
        called after connecting to an existing chat session.

        @param users: A dict mapping user handles to screen names
                      (current users taking part in the conversation)
        """
        pass

    def userJoined(self, userHandle, screenName):
        """
        called when a user has joined the conversation.

        @param userHandle: the user handle (passport) of the user
        @param screenName: the screen name of the user
        """
        pass

    def userLeft(self, userHandle):
        """
        called when a user has left the conversation.

        @param userHandle: the user handle (passport) of the user.
        """
        pass

    def gotMessage(self, message):
        """
        called when we receive a message.

        @param message: the associated MSNMessage object
        """
        pass

    def userTyping(self, message):
        """
        called when we receive the special type of message notifying
        us that a user is typing a message.

        @param message: the associated MSNMessage object
        """
        pass

    def gotSendRequest(self, fileName, fileSize, iCookie, message):
        """
        called when a contact is trying to send us a file.
        To accept or reject this transfer see the
        fileInvitationReply method.

        @param fileName: the name of the file
        @param fileSize: the size of the file
        @param iCookie: the invitation cookie, used so the client can
                        match up your reply with this request.
        @param message: the MSNMessage object which brought about this
                        invitation (it may contain more information)
        """
        pass

    # api calls

    def inviteUser(self, userHandle):
        """
        used to invite a user to the current switchboard server.

        @param userHandle: the user handle (passport) of the desired user.

        @return: A Deferred, the callback for which will be called
                 when the server notifies us that the user has indeed
                 been invited.  The callback argument will be a tuple
                 with 1 element, the sessionID given to the invited user.
                 I'm not sure if this is useful or not.
        """

        id, d = self._createIDMapping()
        self.sendLine("CAL %s %s" % (id, userHandle))
        return d

    def sendMessage(self, message):
        """
        used to send a message.

        @param message: the corresponding MSNMessage object.

        @return: Depending on the value of message.ack.
                 If set to MSNMessage.MESSAGE_ACK or
                 MSNMessage.MESSAGE_NACK a Deferred will be returned,
                 the callback for which will be fired when an ACK or
                 NACK is received - the callback argument will be
                 (None,). If set to MSNMessage.MESSAGE_ACK_NONE then
                 the return value is None.
        """

        if message.ack not in ('A','N'):
            id, d = self._nextTransactionID(), None
        else:
            id, d = self._createIDMapping()
        if message.length == 0:
            message.length = message._calcMessageLen()
        self.sendLine("MSG %s %s %s" % (id, message.ack, message.length))
        # apparently order matters with at least MIME-Version and Content-Type
        self.sendLine('MIME-Version: %s' % message.getHeader('MIME-Version'))
        self.sendLine('Content-Type: %s' % message.getHeader('Content-Type'))
        # send the rest of the headers
        for header in [h for h in message.headers.items() if h[0].lower() not in ('mime-version','content-type')]:
            self.sendLine("%s: %s" % (header[0], header[1]))
        self.transport.write(CR+LF)
        self.transport.write(message.message)
        return d

    def sendTypingNotification(self):
        """
        used to send a typing notification. Upon receiving this
        message the official client will display a 'user is typing'
        message to all other users in the chat session for 10 seconds.
        The official client sends one of these every 5 seconds (I think)
        as long as you continue to type.
        """
        m = MSNMessage()
        m.ack = m.MESSAGE_ACK_NONE
        m.setHeader('Content-Type', 'text/x-msmsgscontrol')
        m.setHeader('TypingUser', self.userHandle)
        m.message = "\r\n"
        self.sendMessage(m)

    def sendFileInvitation(self, fileName, fileSize):
        """
        send an notification that we want to send a file.

        @param fileName: the file name
        @param fileSize: the file size

        @return: A Deferred, the callback of which will be fired
                 when the user responds to this invitation with an
                 appropriate message. The callback argument will be
                 a tuple with 3 elements, the first being 1 or 0
                 depending on whether they accepted the transfer
                 (1=yes, 0=no), the second being an invitation cookie
                 to identify your follow-up responses and the third being
                 the message 'info' which is a dict of information they
                 sent in their reply (this doesn't really need to be used).
                 If you wish to proceed with the transfer see the
                 sendTransferInfo method.
        """
        cookie = self._newInvitationCookie()
        d = Deferred()
        m = MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Application-Name: File Transfer\r\n'
        m.message += 'Application-GUID: %s\r\n' % (classNameToGUID["file transfer"],)
        m.message += 'Invitation-Command: INVITE\r\n'
        m.message += 'Invitation-Cookie: %s\r\n' % str(cookie)
        m.message += 'Application-File: %s\r\n' % fileName
        m.message += 'Application-FileSize: %s\r\n\r\n' % str(fileSize)
        m.ack = m.MESSAGE_ACK_NONE
        self.sendMessage(m)
        self.cookies['iCookies'][cookie] = (d, m)
        return d

    def fileInvitationReply(self, iCookie, accept=1):
        """
        used to reply to a file transfer invitation.

        @param iCookie: the invitation cookie of the initial invitation
        @param accept: whether or not you accept this transfer,
                       1 = yes, 0 = no, default = 1.

        @return: A Deferred, the callback for which will be fired when
                 the user responds with the transfer information.
                 The callback argument will be a tuple with 5 elements,
                 whether or not they wish to proceed with the transfer
                 (1=yes, 0=no), their ip, the port, the authentication
                 cookie (see FileReceive/FileSend) and the message
                 info (dict) (in case they send extra header-like info
                 like Internal-IP, this doesn't necessarily need to be
                 used). If you wish to proceed with the transfer see
                 FileReceive.
        """
        d = Deferred()
        m = MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: %s\r\n' % (accept and 'ACCEPT' or 'CANCEL')
        m.message += 'Invitation-Cookie: %s\r\n' % str(iCookie)
        if not accept:
            m.message += 'Cancel-Code: REJECT\r\n'
        m.message += 'Launch-Application: FALSE\r\n'
        m.message += 'Request-Data: IP-Address:\r\n'
        m.message += '\r\n'
        m.ack = m.MESSAGE_ACK_NONE
        self.sendMessage(m)
        self.cookies['external'][iCookie] = (d, m)
        return d

    def sendTransferInfo(self, accept, iCookie, authCookie, ip, port):
        """
        send information relating to a file transfer session.

        @param accept: whether or not to go ahead with the transfer
                       (1=yes, 0=no)
        @param iCookie: the invitation cookie of previous replies
                        relating to this transfer
        @param authCookie: the authentication cookie obtained from
                           an FileSend instance
        @param ip: your ip
        @param port: the port on which an FileSend protocol is listening.
        """
        m = MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: %s\r\n' % (accept and 'ACCEPT' or 'CANCEL')
        m.message += 'Invitation-Cookie: %s\r\n' % iCookie
        m.message += 'IP-Address: %s\r\n' % ip
        m.message += 'Port: %s\r\n' % port
        m.message += 'AuthCookie: %s\r\n' % authCookie
        m.message += '\r\n'
        m.ack = m.MESSAGE_NACK
        self.sendMessage(m)

class FileReceive(LineReceiver):
    """
    This class provides support for receiving files from contacts.

    @ivar fileSize: the size of the receiving file. (you will have to set this)
    @ivar connected: true if a connection has been established.
    @ivar completed: true if the transfer is complete.
    @ivar bytesReceived: number of bytes (of the file) received.
                         This does not include header data.
    """

    def __init__(self, auth, myUserHandle, file, directory="", overwrite=0):
        """
        @param auth: auth string received in the file invitation.
        @param myUserHandle: your userhandle.
        @param file: A string or file object represnting the file
                     to save data to.
        @param directory: optional parameter specifiying the directory.
                          Defaults to the current directory.
        @param overwrite: if true and a file of the same name exists on
                          your system, it will be overwritten. (0 by default)
        """
        self.auth = auth
        self.myUserHandle = myUserHandle
        self.fileSize = 0
        self.connected = 0
        self.completed = 0
        self.directory = directory
        self.bytesReceived = 0
        self.overwrite = overwrite

        # used for handling current received state
        self.state = 'CONNECTING'
        self.segmentLength = 0
        self.buffer = ''

        if isinstance(file, types.StringType):
            path = os.path.join(directory, file)
            if os.path.exists(path) and not self.overwrite:
                log.msg('File already exists...')
                raise IOError, "File Exists" # is this all we should do here?
            self.file = open(os.path.join(directory, file), 'wb')
        else:
            self.file = file

    def connectionMade(self):
        self.connected = 1
        self.state = 'INHEADER'
        self.sendLine('VER MSNFTP')

    def connectionLost(self, reason):
        self.connected = 0
        self.file.close()

    def parseHeader(self, header):
        """ parse the header of each 'message' to obtain the segment length """

        if ord(header[0]) != 0: # they requested that we close the connection
            self.transport.loseConnection()
            return
        try:
            extra, factor = header[1:]
        except ValueError:
            # munged header, ending transfer
            self.transport.loseConnection()
            raise
        extra  = ord(extra)
        factor = ord(factor)
        return factor * 256 + extra

    def lineReceived(self, line):
        temp = line.split()
        if len(temp) == 1:
            params = []
        else:
            params = temp[1:]
        cmd = temp[0]
        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler:
            handler(params) # try/except
        else:
            self.handle_UNKNOWN(cmd, params)

    def rawDataReceived(self, data):
        bufferLen = len(self.buffer)
        if self.state == 'INHEADER':
            delim = 3-bufferLen
            self.buffer += data[:delim]
            if len(self.buffer) == 3:
                self.segmentLength = self.parseHeader(self.buffer)
                if not self.segmentLength:
                    return # hrm
                self.buffer = ""
                self.state = 'INSEGMENT'
            extra = data[delim:]
            if len(extra) > 0:
                self.rawDataReceived(extra)
            return

        elif self.state == 'INSEGMENT':
            dataSeg = data[:(self.segmentLength-bufferLen)]
            self.buffer += dataSeg
            self.bytesReceived += len(dataSeg)
            if len(self.buffer) == self.segmentLength:
                self.gotSegment(self.buffer)
                self.buffer = ""
                if self.bytesReceived == self.fileSize:
                    self.completed = 1
                    self.buffer = ""
                    self.file.close()
                    self.sendLine("BYE 16777989")
                    return
                self.state = 'INHEADER'
                extra = data[(self.segmentLength-bufferLen):]
                if len(extra) > 0:
                    self.rawDataReceived(extra)
                return

    def handle_VER(self, params):
        checkParamLen(len(params), 1, 'VER')
        if params[0].upper() == "MSNFTP":
            self.sendLine("USR %s %s" % (self.myUserHandle, self.auth))
        else:
            log.msg('they sent the wrong version, time to quit this transfer')
            self.transport.loseConnection()

    def handle_FIL(self, params):
        checkParamLen(len(params), 1, 'FIL')
        try:
            self.fileSize = int(params[0])
        except ValueError: # they sent the wrong file size - probably want to log this
            self.transport.loseConnection()
            return
        self.setRawMode()
        self.sendLine("TFR")

    def handle_UNKNOWN(self, cmd, params):
        log.msg('received unknown command (%s), params: %s' % (cmd, params))

    def gotSegment(self, data):
        """ called when a segment (block) of data arrives. """
        self.file.write(data)

class FileSend(LineReceiver):
    """
    This class provides support for sending files to other contacts.

    @ivar bytesSent: the number of bytes that have currently been sent.
    @ivar completed: true if the send has completed.
    @ivar connected: true if a connection has been established.
    @ivar targetUser: the target user (contact).
    @ivar segmentSize: the segment (block) size.
    @ivar auth: the auth cookie (number) to use when sending the
                transfer invitation
    """

    def __init__(self, file):
        """
        @param file: A string or file object represnting the file to send.
        """

        if isinstance(file, types.StringType):
            self.file = open(file, 'rb')
        else:
            self.file = file

        self.fileSize = 0
        self.bytesSent = 0
        self.completed = 0
        self.connected = 0
        self.targetUser = None
        self.segmentSize = 2045
        self.auth = randint(0, 2**30)
        self._pendingSend = None # :(

    def connectionMade(self):
        self.connected = 1

    def connectionLost(self, reason):
        if self._pendingSend.active():
            self._pendingSend.cancel()
            self._pendingSend = None
        if self.bytesSent == self.fileSize:
            self.completed = 1
        self.connected = 0
        self.file.close()

    def lineReceived(self, line):
        temp = line.split()
        if len(temp) == 1:
            params = []
        else:
            params = temp[1:]
        cmd = temp[0]
        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler:
            handler(params)
        else:
            self.handle_UNKNOWN(cmd, params)

    def handle_VER(self, params):
        checkParamLen(len(params), 1, 'VER')
        if params[0].upper() == "MSNFTP":
            self.sendLine("VER MSNFTP")
        else: # they sent some weird version during negotiation, i'm quitting.
            self.transport.loseConnection()

    def handle_USR(self, params):
        checkParamLen(len(params), 2, 'USR')
        self.targetUser = params[0]
        if self.auth == int(params[1]):
            self.sendLine("FIL %s" % (self.fileSize))
        else: # they failed the auth test, disconnecting.
            self.transport.loseConnection()

    def handle_TFR(self, params):
        checkParamLen(len(params), 0, 'TFR')
        # they are ready for me to start sending
        self.sendPart()

    def handle_BYE(self, params):
        self.completed = (self.bytesSent == self.fileSize)
        self.transport.loseConnection()

    def handle_CCL(self, params):
        self.completed = (self.bytesSent == self.fileSize)
        self.transport.loseConnection()

    def handle_UNKNOWN(self, cmd, params):
        log.msg('received unknown command (%s), params: %s' % (cmd, params))

    def makeHeader(self, size):
        """ make the appropriate header given a specific segment size. """
        quotient, remainder = divmod(size, 256)
        return chr(0) + chr(remainder) + chr(quotient)

    def sendPart(self):
        """ send a segment of data """
        if not self.connected:
            self._pendingSend = None
            return # may be buggy (if handle_CCL/BYE is called but self.connected is still 1)
        data = self.file.read(self.segmentSize)
        if data:
            dataSize = len(data)
            header = self.makeHeader(dataSize)
            self.bytesSent += dataSize
            self.transport.write(header + data)
            self._pendingSend = reactor.callLater(0, self.sendPart)
        else:
            self._pendingSend = None
            self.completed = 1

# mapping of error codes to error messages
errorCodes = {

    200 : "Syntax error",
    201 : "Invalid parameter",
    205 : "Invalid user",
    206 : "Domain name missing",
    207 : "Already logged in",
    208 : "Invalid username",
    209 : "Invalid screen name",
    210 : "User list full",
    215 : "User already there",
    216 : "User already on list",
    217 : "User not online",
    218 : "Already in mode",
    219 : "User is in the opposite list",
    223 : "Too many groups",
    224 : "Invalid group",
    225 : "User not in group",
    229 : "Group name too long",
    230 : "Cannot remove group 0",
    231 : "Invalid group",
    280 : "Switchboard failed",
    281 : "Transfer to switchboard failed",

    300 : "Required field missing",
    301 : "Too many FND responses",
    302 : "Not logged in",

    500 : "Internal server error",
    501 : "Database server error",
    502 : "Command disabled",
    510 : "File operation failed",
    520 : "Memory allocation failed",
    540 : "Wrong CHL value sent to server",

    600 : "Server is busy",
    601 : "Server is unavaliable",
    602 : "Peer nameserver is down",
    603 : "Database connection failed",
    604 : "Server is going down",
    605 : "Server unavailable",

    707 : "Could not create connection",
    710 : "Invalid CVR parameters",
    711 : "Write is blocking",
    712 : "Session is overloaded",
    713 : "Too many active users",
    714 : "Too many sessions",
    715 : "Not expected",
    717 : "Bad friend file",
    731 : "Not expected",

    800 : "Requests too rapid",

    910 : "Server too busy",
    911 : "Authentication failed",
    912 : "Server too busy",
    913 : "Not allowed when offline",
    914 : "Server too busy",
    915 : "Server too busy",
    916 : "Server too busy",
    917 : "Server too busy",
    918 : "Server too busy",
    919 : "Server too busy",
    920 : "Not accepting new users",
    921 : "Server too busy",
    922 : "Server too busy",
    923 : "No parent consent",
    924 : "Passport account not yet verified"

}

# mapping of status codes to readable status format
statusCodes = {

    STATUS_ONLINE  : "Online",
    STATUS_OFFLINE : "Offline",
    STATUS_HIDDEN  : "Appear Offline",
    STATUS_IDLE    : "Idle",
    STATUS_AWAY    : "Away",
    STATUS_BUSY    : "Busy",
    STATUS_BRB     : "Be Right Back",
    STATUS_PHONE   : "On the Phone",
    STATUS_LUNCH   : "Out to Lunch"

}

# mapping of list ids to list codes
listIDToCode = {

    FORWARD_LIST : 'fl',
    BLOCK_LIST   : 'bl',
    ALLOW_LIST   : 'al',
    REVERSE_LIST : 'rl'

}

# mapping of list codes to list ids
listCodeToID = {}
for id,code in listIDToCode.items():
    listCodeToID[code] = id

del id, code

# Mapping of class GUIDs to simple english names
guidToClassName = {
    "{5D3E02AB-6190-11d3-BBBB-00C04F795683}": "file transfer",
    }

# Reverse of the above
classNameToGUID = {}
for guid, name in guidToClassName.iteritems():
    classNameToGUID[name] = guid
