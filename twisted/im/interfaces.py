# -*- Python -*-
"""Pan-protocol chat client.

Stability: incendiary, work in progress.
"""
from twisted.python.components import Interface

import locals

# (Random musings, may not reflect on current state of code:)
#
# Accounts have Protocol components (clients)
# Persons have Conversation components
# Groups have GroupConversation components
# Persons and Groups are associated with specific Accounts
# At run-time, Clients/Accounts are slaved to a User Interface
#   (Note: User may be a bot, so don't assume all UIs are built on gui toolkits)


class IAccount(Interface):
    """I represent a user's account with a chat service.

    @cvar gatewayType: Identifies the protocol used by this account.
    @type gatewayType: string

    @ivar client: The Client currently connecting to this account, if any.
    @type client: L{IClient}
    """

    def __init__(self, accountName, autoLogin, username, password, host, port):
        """
        @type accountName: string
        @param accountName: A name to refer to the account by locally.
        @type autoLogin: boolean
        @type username: string
        @type password: string
        @type host: string
        @type port: integer
        """

    def isOnline(self):
        """Am I online?

        @returntype: boolean
        """

    def logOn(self, chatui):
        """Go on-line.

        @type chatui: Implementor of C{IChatUI}

        @returntype: Deferred L{Client}
        """

    def logOff(self):
        """Sign off.
        """

    def getGroup(self, groupName):
        """
        @returntype: L{Group<IGroup>}
        """

    def getPerson(self, personName):
        """
        @returntype: L{Person<IPerson>}
        """

class IClient(Interface):
    """
    @ivar account: The Account I am a Client for.
    @type account: L{IAccount}
    """
    def __init__(self, account, chatui, logonDeferred):
        """
        @type account: L{IAccount}
        @type chatui: L{IChatUI}
        @param logonDeferred: Will be called back once I am logged on.
        @type logonDeferred: L{Deferred<twisted.internet.defer.Deferred>}
        """

    def joinGroup(self, groupName):
        """
        @param groupName: The name of the group to join.
        @type groupName: string
        """

    def leaveGroup(self, groupName):
        """
        @param groupName: The name of the group to leave.
        @type groupName: string
        """

    def getGroupConversation(self, name,hide=0):
        pass

    def getPerson(self,name):
        pass


class IPerson(Interface):
    def __init__(self, name, account):
        """Initialize me.

        @param name: My name, as the server knows me.
        @type name: string
        @param account: The account I am accessed through.
        @type account: I{Account}
        """

    def isOnline(self):
        """Am I online right now?

        @returntype: boolean
        """

    def getStatus(self):
        """What is my on-line status?

        @returns: L{locals.StatusEnum}
        """

    def getIdleTime(self):
        """
        @returntype: string (XXX: How about a scalar?)
        """

    def sendMessage(self, text, metadata=None):
        """Send a message to this person.

        @type text: string
        @type metadata: dict
        """


class IGroup(Interface):
    """A group which you may have a conversation with.

    Groups generally have a loosely-defined set of members, who may
    leave and join at any time.

    @ivar name: My name, as the server knows me.
    @type name: string
    @ivar account: The account I am accessed through.
    @type account: I{Account<IAccount>}
    """

    def __init__(self, name, account):
        """Initialize me.

        @param name: My name, as the server knows me.
        @type name: string
        @param account: The account I am accessed through.
        @type account: I{Account<IAccount>}
        """

    def setTopic(self, text):
        """Set this Groups topic on the server.

        @type text: string
        """

    def sendGroupMessage(self, text, metadata=None):
        """Send a message to this group.

        @type text: string

        @type metadata: dict
        @param metadata: Valid keys for this dictionary include:
        
            style: associated with one of:
                emote: indicates this is an action
        """

    def join(self):
        pass

    def leave(self):
        """Depart this group"""


class IConversation(Interface):
    """A conversation with a specific person."""
    def __init__(self, person, chatui):
        """
        @type person: L{IPerson}
        """

    def show(self):
        """doesn't seem like it belongs in this interface."""

    def hide(self):
        """nor this neither."""

    def sendText(self, text, metadata):
        pass

    def showMessage(self, text, metadata):
        pass

    def changedNick(self, person, newnick):
        """
        @param person: XXX Shouldn't this always be Conversation.person?
        """

class IGroupConversation(Interface):
    def show(self):
        """doesn't seem like it belongs in this interface."""

    def hide(self):
        """nor this neither."""

    def sendText(self, text, metadata):
        pass

    def showGroupMessage(self, sender, text, metadata):
        pass

    def setGroupMembers(self, members):
        """Sets the list of members in the group and displays it to the user
        """

    def setTopic(self, topic, author):
        """Displays the topic (from the server) for the group conversation window

        @type topic: string
        @type author: string (XXX: Not Person?)
        """

    def memberJoined(self, member):
        """Adds the given member to the list of members in the group conversation
        and displays this to the user

        @type member: string (XXX: Not Person?)
        """

    def memberChangedNick(self, oldnick, newnick):
        """Changes the oldnick in the list of members to newnick and displays this
        change to the user

        @type oldnick: string (XXX: Not Person?)
        @type newnick: string
        """

    def memberLeft(self, member):
        """Deletes the given member from the list of members in the group
        conversation and displays the change to the user

        @type member: string (XXX: Not Person?)
        """


class IChatUI(Interface):
    def registerAccountClient(self, client):
        """Notifies user that an account has been signed on to.

        @type client: L{Client<IClient>}
        """

    def unregisterAccountClient(self, client):
        """Notifies user that an account has been signed off or disconnected

        @type client: L{Client<IClient>}
        """

    def getContactsList(self):
        """
        @returntype: L{ContactsList}
        """

    # WARNING: You'll want to be polymorphed into something with
    # intrinsic stoning resistance before continuing.

    def getConversation(self, person, Class, stayHidden=0):
        """For the given person object, returns the conversation window
        or creates and returns a new conversation window if one does not exist.

        @type person: L{Person<IPerson>}
        @type Class: L{Conversation<IConversation>} class
        @type stayHidden: boolean

        @returntype: L{Conversation<IConversation>}
        """

    def getGroupConversation(self,group,Class,stayHidden=0):
        """For the given group object, returns the group conversation window or
        creates and returns a new group conversation window if it doesn't exist.

        @type group: L{Group<interfaces.IGroup>}
        @type Class: L{Conversation<interfaces.IConversation>} class
        @type stayHidden: boolean

        @returntype: L{GroupConversation<interfaces.IGroupConversation>}
        """

    def getPerson(self, name, client):
        """Get a Person for a client.

        Duplicates L{IAccount.getPerson}.

        @type name: string
        @type client: L{Client<IClient>}

        @returntype: L{Person<IPerson>}
        """

    def getGroup(self, name, client):
        """Get a Group for a client.

        Duplicates L{IAccount.getGroup}.

        @type name: string
        @type client: L{Client<IClient>}

        @returntype: L{Group<IGroup>}
        """

    def contactChangedNick(self, oldnick, newnick):
        """For the given person, changes the person's name to newnick, and
        tells the contact list and any conversation windows with that person
        to change as well.

        @type oldnick: string
        @type newnick: string
        """
