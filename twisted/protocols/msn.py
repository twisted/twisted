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
#

"""
MSNP7 Protocol (client only)

Stability: unstable.

This module provides support for clients using the MSN Protocol (MSNP7).
There are basically 3 servers involved in any MSN session:

  1. I{Dispatch server}

    The MSNDispatchClient class handles connections to the dispatch server,
    which basically delegates users to a suitable notification server.

    You will want to subclass this and handle the gotReferral method appropriately.
    
  2. I{Notification Server}

    The MSNNotificationClient class handles connections to the notification server,
    which acts as a session server (state updates, message negotiation etc...)

  3. I{Switcboard Server}

    The MSNSwitchboardClient handles connections to switchboard servers which are used
    to conduct conversations with other users.

There are also two classes (MSNFileSend and MSNFileReceive) used for file transfers.

Clients handle events in two ways.

  - each client request requiring a response will return a Deferred, the callback for same will be fired
    when the server sends the required response
    .
  - Events which are not in response to any client request have respective methods
    which should be overridden and handled in an adequate manner

Most client request callbacks require more than one argument, and since Deferreds can only pass
the callback one result, most of the time the callback argument will be a tuple of values (documented in
the respective request method). To make reading/writing code easier, callbacks can be defined in a number of ways
to handle this 'cleanly'. One way would be to define methods like: def callBack(self, (arg1, arg2, arg)): ... another
way would be to do something like d.addCallback(lambda result: myCallback(*result)).

If the server sends an error response to a client request, the errback of the
corresponding Deferred will be called, the argument being the corresponding error code.

B{NOTE}
Due to the lack of an 'official' spec for MSNP7, extra checking than may be deemed necessary often
takes place considering the server is never 'wrong'. Thus, if gotBadLine (in any of the 3 main clients)
is called, or an MSNProtocolError is raised, it's probably a good idea to submit a bug report. ;)

TODO
====
- check message hooks with invalid x-msgsinvite messages.
- font handling
- create factories for each respective client

@author: U{Sam Jordan<mailto:sam@twistedmatrix.com>}
"""

from __future__ import nested_scopes

# Sibling imports
from basic import LineReceiver

# Twisted imports
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.python import log

# System imports
import md5, types, operator, os
from random import randint
from urllib import quote, unquote

MSN_PROTOCOL_VERSION  = "MSNP7"             # protocol version
MSN_PORT               = 1863               # default dispatch server port
MSN_MAX_MESSAGE        = 1664               # max message length
MSN_CHALLENGE_STR      = "Q1P7W2E4J9R8U3S5" # used for server challenges

# list constants
FORWARD_LIST = 'fl'
ALLOW_LIST   = 'al'
REVERSE_LIST = 'rl'
BLOCK_LIST   = 'bl'

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

def checkParamLen(num, expected, cmd, error=None):
    if error == None: error = "Invalid Number of Parameters for %s" % cmd
    if num != expected: raise MSNProtocolError, error

class MSNProtocolError(Exception):
    """ This Exception is basically used for debugging purposes, as the
        official MSN server should never send anything _wrong_ and nobody in
        their right mind would run their B{own} MSN server...if it is raised by default
        command handlers (handle_BLAH) the error will be logged.
    """
    pass

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
    @ivar ack: This variable is used to tell the server how to respond once the message
               has been sent.  If set to MESSAGE_ACK (default) the server will respond with an ACK
               upon receiving the message, if set to MESSAGE_NACK the server will respond with
               a NACK upon failure to receive the message.  If set to MESSAGE_ACK_NONE the server
               will do nothing.  This is relevant for the return value of MSNSwitchboardClient.sendMessage (which will return
               a Deferred if ack is set to either MESSAGE_ACK or MESSAGE_NACK and will fire when the respective
               ACK or NCK is received).  If set to MESSAGE_ACK_NONE sendMessage will return None.
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
        """ used to calculte the number to send
            as the message length when sending a message.
        """
        return reduce(operator.add, [len(x[0]) + len(x[1]) + 4  for x in self.headers.items()]) + len(self.message) + 2

    def setHeader(self, header, value):
        """ set the desired header """
        self.headers[header] = value

    def getHeader(self, header):
        """ get the desired header value
            @raise KeyError: if no such header exists.
        """
        return self.headers[header]

    def hasHeader(self, header):
        """ check to see if the desired header exists """
        return self.headers.has_key(header)

    def getMessage(self):
        """ return the message - not including headers """
        return self.message

    def setMessage(self, message):
        """ set the message text """
        self.message = message

class MSNContact:
    
    """ This class represents a contact (user).

        @ivar userHandle: The contact's user handle (passport).
        @ivar screenName: The contact's screen name.
        @ivar group: The group ID.
        @type group: int if contact is in a group, None otherwise.
        @ivar status: The contact's status code.
        @type status: str if contact's status is known, None otherwise.

        @ivar homePhone: The contact's home phone number.
        @type homePhone: str if known, otherwise None.
        @ivar workPhone: The contact's work phone number.
        @type workPhone: str if known, otherwise None.
        @ivar mobilePhone: The contact's mobile phone number.
        @type mobilePhone: str if known, otherwise None.
        @ivar hasPager: Whether or not this user has a mobile pager (true=yes, false=no)
    """
    
    def __init__(self, userHandle="", screenName="", listType=None, group=None, status=None):
        self.userHandle = userHandle
        self.screenName = screenName
        self.list  = listType     # list ('fl','rl','bl','al')
        self.group = group        # group id (if applicable)
        self.status = status      # current status

        # phone details
        self.homePhone   = None
        self.workPhone   = None
        self.mobilePhone = None
        self.hasPager   = None

    def setPhone(self, phoneType, value):
        """ set phone numbers/values for this specific user ..
            for phoneType check the *_PHONE constants and HAS_PAGER """

        t = phoneType.upper()
        if t == HOME_PHONE: self.homePhone = value
        elif t == WORK_PHONE: self.workPhone = value
        elif t == MOBILE_PHONE: self.mobilePhone = value
        elif t == HAS_PAGER: self.hasPager = value
        else: raise ValueError, "Invalid Phone Type"

class MSNContactList:
    """ This class represents a basic MSN contact list.

        @ivar contacts: The forward list (users on my list)
        @type contacts: dict (mapping user handles to MSNContact objects)
        
        @ivar authorizedContacts: Contacts that I have allowed to be notified when
                                  my state changes (allow list)
        @type authorizedContacts: dict (mapping user handles to MSNContact objects)
        
        @ivar reverseContacts: Contacts who have added me to their list
        @type reverseContacts: dict (mapping user handles to MSNContact objects)
        
        @ivar blockedContacts: Contacts not allowed to see state changes nor talk to me
        @type blockedContacts: dict (mapping user handles to MSNContact objects)
        
        @ivar version: The current contact list version (used for list syncing)
        @ivar groups: a mapping of group ids to group names (groups can only exist on the forward list)
        @type groups: dict

        B{Note}: This is used only for storage and doesn't effect the server's contact list.
    """

    def __init__(self):
        self.contacts = {}
        self.authorizedContacts   = {}
        self.reverseContacts = {}
        self.blockedContacts   = {}
        self.version = 0
        self.groups = {}

    def addContact(self, listType, contact, force=0):
        """ Add a contact to the desired list.
            @param listType: Which underlying contact list to add the user to:
              - FORWARD_LIST - 'B{fl}': the forward list
              - ALLOW_LIST   - 'B{al}': the allow list
              - REVERSE_LIST - 'B{rl}': the reverse list
              - BLOCK_LIST   - 'B{bl}': the block list
              The above are defined in the *_LIST constants.
            @param contact: the contact to add
            @type contact: MSNContact object
            @param force: Should we overwrite an existing contact? (1=yes, 0=no(default))

            NOTE: this changes nothing on the server, it only effects _this_ list.
        """
        
        listType = listType.lower()
        if listType == 'rl':
            if not self.reverseContacts.has_key(contact.userHandle) or force:
                self.reverseContacts[contact.userHandle] = contact
                return 1
            return 0
        elif listType == 'bl':
            if not self.blockedContacts.has_key(contact.userHandle) or force:
                self.blockedContacts[contact.userHandle] = contact
                return 1
            return 0
        elif listType == 'al':
            if not self.authorizedContacts.has_key(contact.userHandle) or force:
                self.authorizedContacts[contact.userHandle] = contact
                return 1
            return 0
        elif listType == 'fl':
            if not self.contacts.has_key(contact.userHandle) or force:
                self.contacts[contact.userHandle] = contact
                return 1
            return 0
        else: raise ValueError, "Invalid Contact List Type"

    def removeContact(self, listType, contact):
        """ Remove a contact from the desired list.
            @param listType: Which underlying contact list to remove the user from:
              - FORWARD_LIST - 'B{fl}': the forward list
              - ALLOW_LIST   - 'B{al}': the allow list
              - REVERSE_LIST - 'B{rl}': the reverse list
              - BLOCK_LIST   - 'B{bl}': the block list
              The above are defined in the *_LIST constants.
            @param contact: the contact to remove
            @type contact: MSNContact object

            NOTE: this changes nothing on the server, it only effects _this_ list.
        """
        
        listType = listType.lower()
        if listType == 'rl':
            try:
                del self.reverseContacts[contact.userHandle] 
                return 1
            except KeyError: return 0
        elif listType == 'bl':
            try:
                del self.blockedContacts[contact.userHandle]
                return 1
            except KeyError: return 0
        elif listType == 'al':
            try:
                del self.authorizedContacts[contact.userHandle]
                return 1
            except KeyError: return 0
        elif listType == 'fl':
            try:
                del self.contacts[contact.userHandle]
                return 1
            except KeyError: return 0
        else: raise ValueError, "Invalid UserList Type"

class MSNEventBase(LineReceiver):
    """ This class provides support for handling / dispatching events and is the
        base class of the three main client protocols (MSNDispatchClient, MSNNotificationClient,
        MSNSwitchboardClient) """

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
        """ Fire the callback for the given id
            if one exists and return 1, else return false """
        if self.ids.has_key(id):
            self.ids[id][0].callback(args)
            del self.ids[id]
            return 1
        return 0

    def _nextTransactionID(self):
        """ return a usable transaction ID """
        self.currentID += 1
        if self.currentID > 1000: self.currentID = 1
        return self.currentID

    def _createIDMapping(self, data=None):
        """ return a unique transaction ID that is mapped internally to a
            deferred .. also store arbitrary data if it is needed """
        id = self._nextTransactionID()
        d = Deferred()
        self.ids[id] = (d, data)
        return (id, d)

    def checkMessage(self, message):
        """ process received messages to check for file invitations and typing notifications
            and other control type messages """
        raise NotImplementedError

    def lineReceived(self, line):
        if self.currentMessage:
            self.currentMessage.readPos += len(line+CR+LF)
            if line == "":
                self.setRawMode()
                if self.currentMessage.readPos == self.currentMessage.length: self.rawDataReceived("") # :(
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
            raise MSNProtocolError, "Invalid Message"

        if len(cmd) != 3: raise MSNProtocolError, "Invalid Command"
        if cmd.isdigit():
            if self.ids.has_key(params.split()[0]):
                self.ids[id].errback(int(cmd))
                del self.ids[id]
                return
            else:       # we received an error which doesn't map to a sent command
                self.gotError(int(cmd))
                return

        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler:
            try: handler(params.split())
            except MSNProtocolError, why: self.gotBadLine(line, why)
        else:
            self.handle_UNKNOWN(cmd, params.split())

    def rawDataReceived(self, data):
        extra = ""
        self.currentMessage.readPos += len(data)
        diff = self.currentMessage.readPos - self.currentMessage.length
        if diff > 0:
            self.currentMessage.message += data[:-diff]
            extra = data[diff:]
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
        except ValueError: raise MSNProtocolError, "Invalid Parameter for MSG length argument"
        self.currentMessage = MSNMessage(length=messageLen, userHandle=params[0], screenName=unquote(params[1]))

    def handle_UNKNOWN(self, cmd, params):
        """ implement me in subclasses if you want to handle unknown events """
        log.msg("Received unknown command (%s), params: %s" % (cmd, params))

    ### callbacks

    def gotMessage(self, message):
        """ called when we receive a message - override in notification and switchboard clients """
        raise NotImplementedError

    def gotBadLine(self, line, why):
        """ called when a handler notifies me that this line is broken """
        log.msg('Error in line: %s (%s)' % (line, why))

    def gotError(self, errorCode):
        """ called when the server sends an error which is not in response to a sent
            command (ie. it has no matching transaction ID) """
        log.msg('Error %s' % (errorCodes[errorCode]))

class MSNDispatchClient(MSNEventBase):
    """ This class provides support for clients connecting to the dispatch server
        @ivar userHandle: your user handle (passport) needed before connecting.
    """
    
    userHandle = ""

    def connectionMade(self):
        MSNEventBase.connectionMade(self)
        self.sendLine('VER %s %s' % (self._nextTransactionID(), MSN_PROTOCOL_VERSION))

    ### protocol command handlers ( there is no need to override these )

    def handle_VER(self, params):
        versions = params[1:]
        if versions is None or versions[0].upper() != MSN_PROTOCOL_VERSION:
            self.transport.loseConnection()
            raise MSNProtocolError, "Version Mismatch"
        id = self._nextTransactionID()
        self.sendLine("INF %s" % id)

    def handle_INF(self, params):
        try:
            mechanism = params[1]
        except IndexError:
            raise MSNProtocolError, "Invalid parameters for INF"
        if mechanism.upper() != "MD5":
            self.transport.loseConnection()
            raise MSNProtocolError, "Unknown Auth Mechanism Specified by Server"
        id = self._nextTransactionID()
        self.sendLine("USR %s MD5 I %s" % (id, self.userHandle))

    def handle_XFR(self, params):
        if len(params) < 4: raise MSNProtocolError, "Invalid number of parameters for XFR"
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
        """ called when we get a referral to the notification server.

            @param host: the notification server's hostname
            @param port: the port to connect to
        """
        pass

class MSNNotificationClient(MSNEventBase):
    """ This class provides support for clients connecting to the notification server.
        @ivar userHandle: your user handle.
        @ivar screenName: your screen name
        @ivar password: MSN password
    """
    def __init__(self, currentID=0):
        MSNEventBase.__init__(self)
        self.userHandle = ""
        self.screenName = ""
        self.password = ""
        self.currentID = currentID

        # SYN/LST buffering
        self.listState = (None, None) # keep last id and whether or not it was the end of the LST
        self._pendingLists  = {}
        self._pendingState  = {}
        self._pendingGroups = {}

    def connectionMade(self):
        MSNEventBase.connectionMade(self)
        self.sendLine("VER %s %s" % (self._nextTransactionID(), MSN_PROTOCOL_VERSION))

    def _createUserFromListReply(self, params):
        numParams = len(params)
        if numParams == 6:
            if params[0] == "FL": raise MSNProtocolError, "Invalid Parameters for LST"
            user = MSNContact(userHandle=params[4], screenName=unquote(params[5]), listType=params[0])
            return user
        elif numParams == 7:
            if params[0] != "FL": raise MSNProtocolError, "Invalid Parameters for LST"
            user = MSNContact(userHandle=params[4], screenName=unquote(params[5]), listType='FL', group=int(params[6]))
            return user
        elif numParams == 4:
            return 0
        else:
            raise MSNProtocolError, "Invalid Parameters for LST"

    def _createListFromPending(self, pending):
        """ create an MSNContactList object from the pending list given.
            @param pending: a list of contacts
            @type pending: list of MSNContact objects.
            @return the created contact list
            @rtype MSNContactList
        """
        contactList = MSNContactList()
        map(lambda contact: contactList.addContact(contact.list, contact, force=1), pending)
        return contactList

    def checkMessage(self, message):
        """ hook used for detecting specific notification messages """
        cTypes = [s.lstrip() for s in message.getHeader('Content-Type').split(';')]
        if 'text/x-msmsgsprofile' in cTypes:
            self.gotProfile(message)
            return 0
        return 1

    ### protocol command handlers - no need to override these

    def handle_VER(self, params):
        versions = params[1:]
        if versions is None or versions[0] != MSN_PROTOCOL_VERSION:
            self.transport.loseConnection()
            raise MSNProtocolError, "Invalid version response"
        self.sendLine("INF %s" % self._nextTransactionID())

    def handle_INF(self, params):
        try:
            mechanism = params[1]
        except IndexError:
            raise MSNProtocolError, "Invalid auth mechanism supplied by server"
        if mechanism.upper() != "MD5": raise MSNProtocolError, "Invalid auth mechanism supplied by server"
        self.sendLine("USR %s MD5 I %s" % (self._nextTransactionID(), self.userHandle))

    def handle_USR(self, params):
        if len(params) != 4 and len(params) != 5:
            raise MSNProtocolError, "Invalid Number of Parameters for USR"

        mechanism = params[1]
        if mechanism == "OK":
            self.loggedIn(params[2], unquote(params[3]), int(params[4]))
        elif params[2].upper() == "S":
            self.sendLine("USR %s MD5 S %s" % (self._nextTransactionID(),
                                               md5.md5(params[3]+self.password).hexdigest().lower()))

    def handle_CHG(self, params):
        checkParamLen(len(params), 2, 'CHG')
        id = int(params[0])
        if not self._fireCallback(id, params[1]):
            self.statusChanged(params[1])

    def handle_ILN(self, params):
        checkParamLen(len(params), 4, 'ILN')
        self.gotContactStatus(params[1], params[2], unquote(params[3]))

    def handle_CHL(self, params):
        checkParamLen(len(params), 2, 'CHL')
        self.sendLine("QRY %s msmsgs@msnmsgr.com 32" % self._nextTransactionID())
        self.transport.write(md5.md5(params[1] + MSN_CHALLENGE_STR).hexdigest())

    def handle_QRY(self, params):
        pass

    def handle_NLN(self, params):
        checkParamLen(len(params), 3, 'NLN')
        self.contactStatusChanged(params[0], params[1], unquote(params[2]))

    def handle_FLN(self, params):
        checkParamLen(len(params), 1, 'FLN')
        self.contactOffline(params[0])

    def handle_LST(self, params):
        id = int(params[0])
        if not self.ids.has_key(id): return # XXX: should we raise an exception?
        if self.ids[id][1]:  syn = 1     # part of a syn response
        else: syn = 0                    # part of a lst response

        user = self._createUserFromListReply(params[1:])
        if user:
            if self._pendingLists.has_key(id): self._pendingLists[id].append(user)
            else: self._pendingLists[id] = [user]
            self.listState = (None, id)
        if not syn and (params[3] == params[4]): # end of LST reply
            if params[1] == "FL": # we will now need to handle a BPR as well
                self.listState = (1, id)
            else:
                self._fireCallback(id, self._pendingLists[id])
                del self._pendingLists[id]
                self.listState = (None, None)

        elif syn and (params[1] == 'RL' and params[3] == params[4]): # end of SYN reply
            newList = self._createListFromPending(self._pendingLists[id])
            newList.groups = self._pendingGroups
            newList.version = int(params[2])
            state = self._pendingState
            self._pendingState = {}
            self._pendingGroups = {}
            del self._pendingLists[id]
            self._fireCallback(id, newList, state)
            self.listState = (None, None)

    def handle_BLP(self, params):
        checkParamLen(len(params), 3, 'BLP')
        id = int(params[0])
        if self.ids.has_key(id):
            # check to see if this is in response to a SYN
            if self.ids[id][1]:
                self._pendingState['privacy'] = params[2].lower()
            else:
                self._fireCallback(id, int(params[1]), params[2].lower())

    def handle_GTC(self, params):
        numParams = len(params)
        if numParams < 2: raise MSNProtocolError, "Invalid Number of Paramaters for GTC" # debug
        id = int(params[0])
        if self.ids.has_key(id):
            # check to see if this is in response to a SYN
            if self.ids[id][1]:
                checkParamLen(numParams, 3, 'GTC') # debug
                if params[2].lower() == "a": self._pendingState['autoAdd'] = 0
                elif params[2].lower() == "n": self._pendingState['autoAdd'] = 1
                else: raise MSNProtocolError, "Invalid Paramater for GTC" # debug
            else:
                if params[1].lower() == "a": self._fireCallback(id, 0)
                elif params[1].lower() == "n": self._fireCallback(id, 1)
                else: raise MSNProtocolError, "Invalid Paramater for GTC" # debug

    def handle_SYN(self, params):
        checkParamLen(len(params), 2, 'SYN') # debug
        id = int(params[0])
        if self.ids.has_key(id):
            # check to see if they are about to send the whole list or not
            # ie. if we have the up-to-date contact list
            if self.ids[id][1] == params[1]: self._fireCallback(id, None, None)

    def handle_LSG(self, params):
        checkParamLen(len(params), 7, 'LSG')
        id = int(params[0])
        if self.ids.has_key(id):
            # check to see if this is in response to a SYN
            if self.ids[id][1]:
                self._pendingGroups[int(params[4])] = unquote(params[5])
            else:
                # i'm not even sure if explicitly requesting the list groups works, but we'll
                # add support for it anyway.
                self._pendingGroups[int(params[4])] = unquote(params[5])
                if params[3] == params[4]: # this was the last group
                    self._fireCallback(id, self._pendingGroups, int(params[1]))
                    self._pendingGroups = {}

    def handle_PRP(self, params):
        numParams = len(params)
        if numParams < 3: raise MSNProtocolError, "Invalid Number of Paramaters for PRP" # debug
        id = int(params[0])
        if numParams == 4:
            if not params[2].upper() in ('PHH', 'PHW', 'PHM', 'MOB', 'MBE'):
                raise MSNProtocolError, "Invalid Phone Type" # debug
            # is this a response to a SYN ?
            if self.ids.has_key(id):
                if self.ids[id][1]:
                    self._pendingState[params[2]] = unquote(params[3])
                else:
                    self._fireCallback(id, int(params[1]), unquote(params[3]))

        elif numParams == 3 and self.ids[id][1]:
            # we'll assume this can only happen in response to a SYN
            # (or at least, that's all we'll care about for now)
            self._pendingState[params[2]] = None
        else: raise MSNProtocolError, "Invalid Number of Parameters for PRP" # debug

    def handle_BPR(self, params):
        id = self.listState[1]
        numParams = len(params)
        if numParams == 4:
            if not id:
                self.gotPhoneNumber(int(params[0]), params[1], params[2], unquote(params[3]))
                return
            self._pendingLists[id][-1].setPhone(params[2], unquote(params[3]))
            if self.listState[0]: # handle end of normal list
                self._fireCallback(id, self._pendingLists[id])
                del self._pendingLists[id]
                self.listState = (None, None)

        elif numParams == 3: pass # do nothing if they send no number at the moment
        else: raise MSNProtocolError, "Invalid Number of Parameters for BPR" # debug

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
            raise MSNProtocolError, "Invalid Paramaters for ADD" # debug
        id = int(params[0])
        listType = params[1]
        listVer = int(params[2])
        userHandle = params[3]
        groupID = None
        if numParams == 6: # they sent a group id
            if params[1].upper() != "FL": raise MSNProtocolError, "Only forward list can contain groups" # debug
            groupID = int(params[5])
        if not self._fireCallback(id, listType, userHandle, listVer, groupID):
            self.userAddedMe(userHandle, unquote(params[4]), listVer)

    def handle_REM(self, params):
        numParams = len(params)
        if numParams < 4 or params[1].upper() not in ('AL','BL','FL','RL'):
            raise MSNProtocolError, "Invalid Paramaters for REM" # debug
        id = int(params[0])
        listType = params[1]
        listVer = int(params[2])
        userHandle = params[3]
        groupID = None
        if numParams == 5:
            if params[1] != "FL": raise MSNProtocolError, "Only forward list can contain groups" # debug
            groupID = int(params[4])
        if not self._fireCallback(id, listType, userHandle, listVer, groupID):
            if listType.upper() == "RL": self.userRemovedMe(userHandle, listVer)

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
        if params[0] == "OTH": self.multipleLogin()
        elif params[0] == "SSD": self.serverGoingDown()
        else: raise MSNProtocolError, "Invalid Parameters received for OUT" # debug

    # callbacks

    def loggedIn(self, userHandle, screenName, verified):
        """ called when the client has logged in

            @param userHandle: our userHandle
            @param screenName: our screenName
            @param verified: 1 if our passport has been (verified), 0 if not.
                             (i'm not sure of the significace of this)
            @type verified: int
        """
        pass

    def gotProfile(self, message):
        """ called after logging in when the server sends an initial message with MSN/passport specific
            profile information such as country, number of kids, etc... Check the message headers for the
            specific values.

            @param message: The profile message
        """
        pass

    def statusChanged(self, statusCode):
        """ called when our status changes and it isn't in response to
            a client command.

            @param statusCode: 3-letter status code
        """
        pass

    def gotContactStatus(self, statusCode, userHandle, screenName):
        """ called after loggin in when the server sends status of online contacts.

            @param statusCode: 3-letter status code
            @param userHandle: the contact's user handle (passport)
            @param screenName: the contact's screen name
        """
        pass

    def contactStatusChanged(self, statusCode, userHandle, screenName):
        """ called when we're notified that a contact's status has changed.

            @param statusCode: 3-letter status code
            @param userHandle: the contact's user handle (passport)
            @param screenName: the contact's screen name
        """
        pass

    def contactOffline(self, userHandle):
        """ called when a contact goes offline.

            @param userHandle: the contact's user handle
        """
        pass

    def gotPhoneNumber(self, listVersion, userHandle, phoneType, number):
        """ called when the server sends us phone details about a specific user (for example after
            a user is added the server will send their status, phone details etc ...

            @param listVersion: the new list version
            @param userHandle: the contact's user handle (passport)
            @param phoneType: the specific phoneType (*_PHONE constants or HAS_PAGER)
            @param number: the value/phone number.
        """
        pass

    def userAddedMe(self, userHandle, screenName, listVersion):
        """ called when a user adds me to their list. (ie. they have been added to
            the reverse list.

            @param userHandle: the userHandle of the user
            @param screenName: the screen name of the user
            @param listVersion: the new list version
            @type listVersion: int
        """
        pass

    def userRemovedMe(self, userHandle, listVersion):
        """ called when a user removes us from their contact list (they are no longer on our reverseContacts list
            and changes to the underlying list should be made to reflect this).

            @param userHandle: the contact's user handle (passport)
            @param listVersion: the new list version
        """
        pass

    def gotSwitchboardInvitation(self, sessionID, host, port,
                                 key, userHandle, screenName):
        """ called when we get an invitation to a switchboard server.
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
        """ called when the server says there has been another login
            under our account, the server should disconnect us right away.
        """
        pass

    def serverGoingDown(self):
        """ called when the server has notified us that it is going down for
            maintenance.
        """
        pass

    # api calls

    def changeStatus(self, status):
        """ change my current status.

            @param status: 3-letter status code (as defined by the STATUS_* constants)
            @return: A Deferred, the callback of which will be fired when the server confirms
                     the change of status.  The callback argument will be a tuple with the new status
                     code as the only element.
        """
        
        id, d = self._createIDMapping()
        self.sendLine("CHG %s %s" % (id, status))
        return d

    def requestList(self, listType):
        """ request the desired list type

            @param listType: 2-letter list type (as defined by the *_LIST constants)
            @return: A Deferred, the callback of which will be fired when the list has
                     been retrieved.  The callback argument will be a tuple with the only element
                     being a list of MSNContact objects.
        """
        # this doesn't need to ever be used if you sync and update correctly.
        id, d = self._createIDMapping()
        self.sendLine("LST %s %s" % (id, listType.upper()))
        return d

    def setPrivacyMode(self, privLevel):
        """ set my privacy mode on the server.

            B{Note}: This only keeps the current privacy setting on the server for later
            retrieval, it does not effect the way the server works at all.

            @param privLevel: This parameter can be true, in which case the server will
                              keep the state as 'al' which the official client interprets as ->
                              allow messages from only users on the allow list.  Alternatively
                              it can be false, in which case the server will keep the state as 'bl'
                              which the official client interprets as -> allow messages from all users
                              except those on the block list.

            @return: A Deferred, the callback of which will be fired when the server replies with the
                     new privacy setting.  The callback argument will be a tuple, the 2 elements of which
                     being the list version and either ALLOW_LIST or BLOCK_LIST (the new privacy setting).
        """

        id, d = self._createIDMapping()
        if privLevel: self.sendLine("BLP %s AL" % id)
        else: self.sendLine("BLP %s BL" % id)
        return d

    def syncList(self, version):
        """ used for keeping an up-to-date contact list.

            @param version: The current known list version

            @return: A Deferred, the callback of which will be fired when the server sends an adequate reply.
                     The callback argument will be a tuple with two elements, the new list (MSNContactList) and
                     your current state (a dictionary).  If the version you sent _was_ the latest list version,
                     both elements will be None. To just request the list send a version of 0.
        """
        
        id, d = self._createIDMapping(data=str(version))
        self.sendLine("SYN %s %s" % (id, version))
        return d

    def requestListGroups(self):
        """ Request (forward) list groups.

            @return: A Deferred, the callback for which will be called when the server responds
                     with the list groups.  The callback argument will be a tuple with two elements,
                     a dictionary mapping group IDs to group names and the current list version.
        """
        
        # this doesn't necessarily need to be used if syncing of the lists takes place (which it SHOULD!)
        id, d = self._createIDMapping()
        self.sendLine("LSG %s" % id)
        return d

    def setPhoneDetails(self, phoneType, value):
        """ Set/change my phone numbers stored on the server.

            @param phoneType: phoneType can be one of the following constants - HOME_PHONE, WORK_PHONE,
                              MOBILE_PHONE, HAS_PAGER.  These are pretty self-explanatory, except maybe HAS_PAGER which
                              refers to whether or not you have a pager.
            @param value: for all of the *_PHONE constants the value is a phone number (str), for HAS_PAGER accepted
                          values are 'Y' (for yes) and 'N' (for no).

            @return: A Deferred, the callback for which will be fired when the server confirms the change has been made.
                     The callback argument will be a tuple with 2 elements, the first being the new list version (int) and
                     the second being the new phone number value (str).
        """
        id, d = self._createIDMapping()
        self.sendLine("PRP %s %s %s" % (id, phoneType, quote(value)))
        return d

    def addListGroup(self, name):
        """ used to create a new list group.

            @param name: The desired name of the new group.

            @return: A Deferred, the callbacck for which will be called when the server
                     clarifies that the new group has been created.  The callback argument
                     will be a tuple with 3 elements: the new list version (int), the new group name (str)
                     and the new group ID (int).
        """

        id, d = self._createIDMapping()
        self.sendLine("ADG %s %s 0" % (id, quote(name)))
        return d

    def remListGroup(self, groupID):
        """ used to remove a list group.

        @param groupID: the ID of the desired group to be removed.

        @return: A Deferred, the callback for which will be called when the server
                 clarifies the deletion of the group.  The callback argument will be a tuple
                 with 2 elements: the new list version (int) and the group ID (int) of the removed group.
        """

        id, d = self._createIDMapping()
        self.sendLine("RMG %s %s" % (id, groupID))
        return d

    def renameListGroup(self, groupID, newName):
        """ used to rename an existing list group.

            @param groupID: the ID of the desired group to rename.
            @param newName: the desired new name for the group.

            @return: A Deferred, the callback for which will be called when the server
            clarifies the renaming.  The callback argument will be a tuple of 3 elements,
            the new list version (int), the group id (int) and the new group name (str).
        """
        
        id, d = self._createIDMapping()
        self.sendLine("REG %s %s %s 0" % (id, groupID, quote(newName)))
        return d

    def addContact(self, listType, userHandle, groupID=0):
        """ used to add a contact to the desired list.

            @param listType: 2-letter list type (as defined by the *_LIST constants)
            @param userHandle: the user handle (passport) of the contact that is being added
            @param groupID: the group ID for which to associate this contact with. (default 0 - no group).
                            Groups are only valid in the forward list.

            @return: A Deferred, the callback for which will be called when the server has clarified
                     that the user has been added.  The callback argument will be a tuple with 4 elements:
                     the list type, the contact's user handle, the new list version, and the group id (if relevant,
                     otherwise it will be None)
        """
        
        id, d = self._createIDMapping()
        if listType.upper() == "FL":
            self.sendLine("ADD %s FL %s %s %s" % (id, userHandle, userHandle, groupID))
        else:
            self.sendLine("ADD %s %s %s %s" % (id, listType.upper(), userHandle, userHandle))
        return d

    def remContact(self, listType, userHandle, groupID=0):
        """ used to remove a contact from the desired list.

            @param listType: 2-letter list type (as defined by the *_LIST constants)
            @param userHandle: the user handle (passport) of the contact being removed
            @param groupID: the ID of the group to which this contact belongs (only relevant
                            in the forward list, default is 0)

            @return: A Deferred, the callback for which will be called when the server has clarified
                     that the user has been removed.  The callback argument will be a tuple of 4 elements:
                     the list type, the contact's user handle, the new list version, and the group id (if relevant,
                     otherwise it will be None)
        """
        
        id, d = self._createIDMapping()
        if listType.upper() == "FL":
            self.sendLine("REM %s FL %s %s" % (id, userHandle, groupID))
        else:
            self.sendLine("REM %s %s %s" % (id, listType.upper(), userHandle))
        return d

    def changeScreenName(self, newName):
        """ used to change your current screen name.

            @param newName: the new screen name

            @return: A Deferred, the callback for which will be called when the server sends an adequate
                     reply.  The callback argument will be a tuple of 2 elements: the new list version and
                     the new screen name.
        """

        id, d = self._createIDMapping()
        self.sendLine("REA %s %s %s" % (id, self.userHandle, quote(newName)))
        return d

    def requestSwitchboardServer(self):
        """ used to request a switchboard server to use for conversations.

            @return: A Deferred, the callback for which will be called when the server responds
                     with the switchboard information. The callback argument will be a tuple with
                     3 elements: the host of the switchboard server, the port and a key used for
                     logging in.
        """

        id, d = self._createIDMapping()
        self.sendLine("XFR %s SB" % id)
        return d

    def logOut(self):
        """ used to log out of the notification server.  After running the method
            the server is expected to close the connection.
        """
        
        self.sendLine("OUT")

class MSNSwitchboardClient(MSNEventBase):
    """ this class provides support for clients connecting to a switchboard server.

        Switchboard servers are used for conversations with other people on the MSN network.
        This means that the number of conversations at any given time will be directly proportional
        to the number of connections to varioius switchboard servers.  MSN makes no distinction between
        single and group conversations, so any number of users may be invited to join a specific conversation
        taking place on a switchboard server.

        @ivar key: authorization key, obtained when receiving invitation / requesting switchboard server.
        @ivar userHandle: your user handle (passport)
        @ivar sessionID: unique session ID, used if you are replying to a switchboard invitation
        @ivar reply: set this to 1 in connectionMade or before to signifiy that you are replying to a
                     switchboard invitation.
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
        self._sendInit()

    def connectionLost(self, reason):
        self.cookies['iCookies'] = {}
        self.cookies['external'] = {}
        MSNEventBase.connectionLost(self, reason)

    def _sendInit(self):
        """ send initial data based on whether we are replying to an invitation
            or starting one.
        """
        id = self._nextTransactionID()
        if not self.reply:
            self.sendLine("USR %s %s %s" % (id, self.userHandle, self.key))
        else:
            self.sendLine("ANS %s %s %s %s" % (id, self.userHandle, self.key, self.sessionID))

    def _newInvitationCookie(self):
        self._iCookie += 1
        if self._iCookie > 1000: self._iCookie = 1
        return self._iCookie

    def _checkTyping(self, message, cTypes):
        """ helper method for checkMessage """
        if 'text/x-msmsgscontrol' in cTypes and message.hasHeader('TypingUser'):
            self.userTyping(message)
            return 1

    def _checkFileInvitation(self, message, info):
        """ helper method for checkMessage """
        if not info.get('Application-Name', '').lower() == 'file transfer': return 0
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
        except KeyError: return 0
        accept = (cmd == 'ACCEPT') and 1 or 0
        requested = self.cookies['iCookies'].get(cookie)
        if not requested: return 1
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
        except KeyError: return 0
        accept = (cmd == 'ACCEPT') and 1 or 0
        requested = self.cookies['external'].get(iCookie)
        if not requested: return 1 # we didn't ask for this
        requested[0].callback((accept, ip, port, aCookie, info))
        del self.cookies['external'][iCookie]
        return 1

    def checkMessage(self, message):
        """ hook for detecting any notification type messages (e.g. file transfer) """
        cTypes = [s.lstrip() for s in message.getHeader('Content-Type').split(';')]
        if self._checkTyping(message, cTypes): return 0
        if 'text/x-msmsgsinvite' in cTypes:
            # header like info is sent as part of the message body.
            info = {}
            for line in message.message.split('\r\n'):
                try:
                    key, val = line.split(':')
                    info[key] = val.lstrip()
                except ValueError: continue
            if self._checkFileInvitation(message, info) or self._checkFileInfo(message, info) or self._checkFileResponse(message, info): return 0
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
        id = int(params[0])
        if params[1] == "OK":
            #self._fireCallback(id)
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
        """ called when all login details have been negotiated.
            Messages can now be sent, or new users invited.
        """
        pass

    def gotChattingUsers(self, users):
        """ called after connecting to an existing chat session.

            @param users: A dict mapping usre handles to screen names (current users
                          taking part in the conversation)
        """
        pass

    def userJoined(self, userHandle, screenName):
        """ called when a user has joined the conversation.

            @param userHandle: the user handle (passport) of the user
            @param screenName: the screen name of the user
        """
        pass

    def userLeft(self, userHandle):
        """ called when a user has left the conversation.

            @param userHandle: the user handle (passport) of the user.
        """
        pass

    def gotMessage(self, message):
        """ called when we receive a message.

            @param message: the associated MSNMessage object
        """
        pass

    def userTyping(self, message):
        """ called when we receive the special type of message notifying us that
            a user is typing a message.

            @param message: the associated MSNMessage object
        """
        pass

    def gotSendRequest(self, fileName, fileSize, iCookie, message):
        """ called when a contact is trying to send us a file.  To accept or reject
            this transfer see the fileInvitationReply method.

            @param fileName: the name of the file
            @param fileSize: the size of the file
            @param iCookie: the invitation cookie, used so the client can match up
                            your reply with this request.
            @param message: the MSNMessage object which brought about this invitation
                            (it may contain more information)
        """
        pass

    # api calls

    def inviteUser(self, userHandle):
        """ used to invite a user to the current switchboard server.

            @param userHandle: the user handle (passport) of the desired user.

            @return: A Deferred, the callback for which will be called when the server
                     notifies us that the user has indeed been invited.  The callback argument
                     will be a tuple with 1 element, the sessionID given to the invited user.  I'm
                     not sure if this is useful or not.
        """

        id, d = self._createIDMapping()
        self.sendLine("CAL %s %s" % (id, userHandle))
        return d

    def sendMessage(self, message):
        """ used to send a message.

            @param message: the corresponding MSNMessage object.

            @return: Depending on the value of message.ack.  If set to MSNMessage.MESSAGE_ACK or
                     MSNMessage.MESSAGE_NACK a Deferred will be returned, the callback for which will
                     be fired when an ACK or NCK is received - the callback argument will be (None,).  If set to
                     MSNMessage.MESSAGE_ACK_NONE then the return value is None.
        """

        if message.ack not in ('A','N'): id, d = self._nextTransactionID(), None
        else: id, d = self._createIDMapping()
        if message.length == 0: message.length = message._calcMessageLen()
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
        """ used to send a typing notification.  Upon receiving this message the official
            client will display a 'user is typing' message to all other users in the chat session
            for 10 seconds.  The official client sends one of these every 5 seconds (I think) as long
            as you continue to type.
        """
        m = MSNMessage()
        m.ack = m.MESSAGE_ACK_NONE
        m.setHeader('Content-Type', 'text/x-msmsgscontrol')
        m.setHeader('TypingUser', self.userHandle)
        m.message = "\r\n"
        self.sendMessage(m)

    def sendFileInvitation(self, fileName, fileSize):
        """ send an notification that we want to send a file.

            @param fileName: the file name
            @param fileSize: the file size

            @return: A Deferred, the callback of which will be fired when the user responds to this
                     invitation with an appropriate message.  The callback argument will be a tuple with 3
                     elements, the first being 1 or 0 depending on whether they accepted the transfer (1=yes, 0=no),
                     the second being an invitation cookie to identify your follow-up responses and the third being
                     the message 'info' which is a dict of information they sent in their reply (this doesn't really
                     need to be used).  If you wish to proceed with the transfer see the sendTransferInfo method.
        """
        cookie = self._newInvitationCookie()
        d = Deferred()
        m = MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Application-Name: File Transfer\r\n'
        m.message += 'Application-GUID: {5D3E02AB-6190-11d3-BBBB-00C04F795683}\r\n'
        m.message += 'Invitation-Command: INVITE\r\n'
        m.message += 'Invitation-Cookie: %s\r\n' % str(cookie)
        m.message += 'Application-File: %s\r\n' % fileName
        m.message += 'Application-FileSize: %s\r\n\r\n' % str(fileSize)
        m.ack = m.MESSAGE_ACK_NONE
        self.sendMessage(m)
        self.cookies['iCookies'][cookie] = (d, m)
        return d

    def fileInvitationReply(self, iCookie, accept=1):
        """ used to reply to a file transfer invitation.

            @param iCookie: the invitation cookie of the initial invitation
            @param accept: whether or not you accept this transfer, 1 = yes, 0 = no, default = 1.

            @return: A Deferred, the callback for which will be fired when the user responds with the
                     transfer information. The callback argument will be a tuple with 5 elements, whether
                     or not they wish to proceed with the transfer (1=yes, 0=no), their ip, the port, the
                     authentication cookie (see MSNFileReceive/MSNFileSend) and the message info (dict) (in case they
                     send extra header-like info like Internal-IP, this doesn't necessarily need to be used).
                     If you wish to proceed with the transfer see MSNFileReceive.
        """
        d = Deferred()
        m = MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: %s\r\n' % (accept and 'ACCEPT' or 'CANCEL')
        m.message += 'Invitation-Cookie: %s\r\n' % str(iCookie)
        if not accept: m.message += 'Cancel-Code: REJECT\r\n'
        m.message += 'Launch-Application: FALSE\r\n'
        m.message += 'Request-Data: IP-Address:\r\n'
        m.message += '\r\n'
        m.ack = m.MESSAGE_ACK_NONE
        self.sendMessage(m)
        self.cookies['external'][iCookie] = (d, m)
        return d

    def sendTransferInfo(self, accept, iCookie, authCookie, ip, port):
        """ send information relating to a file transfer session.

            @param accept: whether or not to go ahead with the transfer (1=yes, 0=no)
            @param iCookie: the invitation cookie of previous replies relating to this transfer
            @param authCookie: the authentication cookie obtained from an MSNFileSend instance
            @param ip: your ip
            @param port: the port on which an MSNFileSend protocol is listening.
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

class MSNFileReceive(LineReceiver):
    """ This class provides support for receiving files from contacts.

        @ivar fileSize: the size of the receiving file. (you will have to set this)
        @ivar connected: true if a connection has been established.
        @ivar completed: true if the transfer is complete.
        @ivar bytesReceived: number of bytes (of the file) received.  This does not
                             include header data.
        """

    def __init__(self, auth, myUserHandle, file, directory="", overwrite=0):
        """ @param auth: auth string received in the file invitation.
            @param myUserHandle: your userhandle.
            @param file: A string or file object represnting the file to save data to.
            @param directory: optional parameter specifiying the directory. Defaults to the
                              current directory.
            @param overwrite: if true and a file of the same name exists on your system, it will
                              be overwritten. (0 by default)
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
        if len(temp) == 1: params = []
        else: params = temp[1:]
        cmd = temp[0]
        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler: handler(params) # try/except
        else: self.handle_UNKNOWN(cmd, params)

    def rawDataReceived(self, data):
        bufferLen = len(self.buffer)
        if self.state == 'INHEADER':
            delim = 3-bufferLen
            self.buffer += data[:delim]
            if len(self.buffer) == 3:
                self.segmentLength = self.parseHeader(self.buffer)
                if not self.segmentLength: return # hrm
                self.buffer = ""
                self.state = 'INSEGMENT'
            extra = data[delim:]
            if len(extra) > 0: self.rawDataReceived(extra)
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
                if len(extra) > 0: self.rawDataReceived(extra)
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

class MSNFileSend(LineReceiver):
    """ This class provides support for sending files to other contacts.

        @ivar bytesSent: the number of bytes that have currently been sent.
        @ivar completed: true if the send has completed.
        @ivar connected: true if a connection has been established.
        @ivar targetUser: the target user (contact).
        @ivar segmentSize: the segment (block) size.
        @ivar auth: the auth cookie (number) to use when sending the transfer invitation
    """
    
    def __init__(self, file):
        """ @param file: A string or file object represnting the file to send.
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
        if self._pendingSend:
            self._pendingSend.cancel()
            self._pendingSend = None
        self.connected = 0
        self.file.close()

    def lineReceived(self, line):
        temp = line.split()
        if len(temp) == 1: params = []
        else: params = temp[1:]
        cmd = temp[0]
        handler = getattr(self, "handle_%s" % cmd.upper(), None)
        if handler: handler(params)
        else: self.handle_UNKNOWN(cmd, params)

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

    def handle_UNKNOWN(self, cmd, params): log.msg('received unknown command (%s), params: %s' % (cmd, params))

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
            self.transport.write(header + data)
            self.bytesSent += dataSize
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
    280 : "Switchboard failed",
    281 : "Transfer to switchboard failed",

    300 : "Required field missing",
    302 : "Not logged in",

    500 : "Internal server error",
    501 : "Database server error",
    510 : "File operation failed",
    520 : "Memory allocation failed",
    540 : "Wrong CHL value sent to server",

    600 : "Server is busy",
    601 : "Server is unavaliable",
    602 : "Peer nameserver is down",
    603 : "Database connection failed",
    604 : "Server is going down",

    707 : "Could not create connection",
    711 : "Write is blocking",
    712 : "Session is overloaded",
    713 : "Too many active users",
    714 : "Too many sessions",
    715 : "Not expected",
    717 : "Bad friend file",

    911 : "Authentication failed",
    913 : "Not allowed when offline",
    920 : "Not accepting new users",
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
