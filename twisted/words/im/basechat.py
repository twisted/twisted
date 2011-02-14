# -*- test-case-name: twisted.words.test.test_basechat -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Base classes for Instance Messenger clients.
"""

from twisted.words.im.locals import OFFLINE, ONLINE, AWAY


class ContactsList:
    """A GUI object that displays a contacts list"""
    def __init__(self, chatui):
        """
        @param chatui: ???
        @type chatui: L{ChatUI}
        """
        self.chatui = chatui
        self.contacts = {}
        self.onlineContacts = {}
        self.clients = []

    def setContactStatus(self, person):
        """Inform the user that a person's status has changed.

        @type person: L{Person<interfaces.IPerson>}
        """
        if not self.contacts.has_key(person.name):
            self.contacts[person.name] = person
        if not self.onlineContacts.has_key(person.name) and \
            (person.status == ONLINE or person.status == AWAY):
            self.onlineContacts[person.name] = person
        if self.onlineContacts.has_key(person.name) and \
           person.status == OFFLINE:
            del self.onlineContacts[person.name]

    def registerAccountClient(self, client):
        """Notify the user that an account client has been signed on to.

        @type client: L{Client<interfaces.IClient>}
        """
        if not client in self.clients:
            self.clients.append(client)

    def unregisterAccountClient(self, client):
        """Notify the user that an account client has been signed off
        or disconnected from.

        @type client: L{Client<interfaces.IClient>}
        """
        if client in self.clients:
            self.clients.remove(client)

    def contactChangedNick(self, person, newnick):
        oldname = person.name
        if self.contacts.has_key(oldname):
            del self.contacts[oldname]
            person.name = newnick
            self.contacts[newnick] = person
            if self.onlineContacts.has_key(oldname):
                del self.onlineContacts[oldname]
                self.onlineContacts[newnick] = person


class Conversation:
    """A GUI window of a conversation with a specific person"""
    def __init__(self, person, chatui):
        """
        @type person: L{Person<interfaces.IPerson>}
        @type chatui: L{ChatUI}
        """
        self.chatui = chatui
        self.person = person

    def show(self):
        """Displays the ConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")

    def hide(self):
        """Hides the ConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")

    def sendText(self, text):
        """Sends text to the person with whom the user is conversing.

        @returntype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        self.person.sendMessage(text, None)

    def showMessage(self, text, metadata=None):
        """Display a message sent from the person with whom she is conversing

        @type text: string
        @type metadata: dict
        """
        raise NotImplementedError("Subclasses must implement this method")

    def contactChangedNick(self, person, newnick):
        """Change a person's name.

        @type person: L{Person<interfaces.IPerson>}
        @type newnick: string
        """
        self.person.name = newnick



class GroupConversation:
    """A conversation with a group of people."""
    def __init__(self, group, chatui):
        """
        @type group: L{Group<interfaces.IGroup>}
        @param chatui: ???
        @type chatui: L{ChatUI}
        """
        self.chatui = chatui
        self.group = group
        self.members = []

    def show(self):
        """Displays the GroupConversationWindow."""
        raise NotImplementedError("Subclasses must implement this method")

    def hide(self):
        """Hides the GroupConversationWindow."""
        raise NotImplementedError("Subclasses must implement this method")

    def sendText(self, text):
        """Sends text to the group.

        @type text: string
        @returntype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        self.group.sendGroupMessage(text, None)

    def showGroupMessage(self, sender, text, metadata=None):
        """Displays to the user a message sent to this group from the given sender
        @type sender: string (XXX: Not Person?)
        @type text: string
        @type metadata: dict
        """
        raise NotImplementedError("Subclasses must implement this method")

    def setGroupMembers(self, members):
        """Sets the list of members in the group and displays it to the user
        """
        self.members = members

    def setTopic(self, topic, author):
        """Displays the topic (from the server) for the group conversation window

        @type topic: string
        @type author: string (XXX: Not Person?)
        """
        raise NotImplementedError("Subclasses must implement this method")

    def memberJoined(self, member):
        """Adds the given member to the list of members in the group conversation
        and displays this to the user

        @type member: string (XXX: Not Person?)
        """
        if not member in self.members:
            self.members.append(member)

    def memberChangedNick(self, oldnick, newnick):
        """Changes the oldnick in the list of members to newnick and displays this
        change to the user

        @type oldnick: string
        @type newnick: string
        """
        if oldnick in self.members:
            self.members.remove(oldnick)
            self.members.append(newnick)
            #self.chatui.contactChangedNick(oldnick, newnick)

    def memberLeft(self, member):
        """Deletes the given member from the list of members in the group
        conversation and displays the change to the user

        @type member: string
        """
        if member in self.members:
            self.members.remove(member)


class ChatUI:
    """
    A GUI chat client.

    @type conversations: C{dict} of L{Conversation}.
    @ivar conversations: A cache of all the direct windows.

    @type groupConversations: C{dict} of L{GroupConversation}.
    @ivar groupConversations: A cache of all the group windows.

    @type persons: C{dict} with keys that are a C{tuple} of (C{str},
        L{basesupport.AbstractAccount}) and values that are
        L{Person<interfaces.IPerson>}.
    @ivar persons: A cache of all the users associated with this client.

    @type groups: C{dict} with keys that are a C{tuple} of (C{str},
        L{basesupport.AbstractAccount}) and values that are
        L{Group<interfaces.IGroup>}
    @ivar groups: A cache of all the user groups associated with this client.

    @type onlineClients: C{list} of L{Client<interfaces.IClient>}
    @ivar onlineClients: A list of message sources currently online.

    @type contactsList: L{ContactsList}
    @ivar contactsList: A contacts list.
    """
    def __init__(self):
        self.conversations = {}
        self.groupConversations = {}
        self.persons = {}
        self.groups = {}
        self.onlineClients = []
        self.contactsList = ContactsList(self)


    def registerAccountClient(self, client):
        """
        Notifies user that an account has been signed on to.

        @type client: L{Client<interfaces.IClient>}
        @returns: client, so that I may be used in a callback chain
        """
        print "signing onto", client.accountName
        self.onlineClients.append(client)
        self.contactsList.registerAccountClient(client)
        return client


    def unregisterAccountClient(self, client):
        """
        Notifies user that an account has been signed off or disconnected

        @type client: L{Client<interfaces.IClient>}
        """
        print "signing off from", client.accountName
        self.onlineClients.remove(client)
        self.contactsList.unregisterAccountClient(client)


    def getContactsList(self):
        """
        @returntype: L{ContactsList}
        """
        return self.contactsList


    def getConversation(self, person, Class=Conversation, stayHidden=0):
        """
        For the given person object, returns the conversation window
        or creates and returns a new conversation window if one does not exist.

        @type person: L{Person<interfaces.IPerson>}
        @type Class: L{Conversation<interfaces.IConversation>} class
        @type stayHidden: boolean

        @returntype: L{Conversation<interfaces.IConversation>}
        """
        conv = self.conversations.get(person)
        if not conv:
            conv = Class(person, self)
            self.conversations[person] = conv
        if stayHidden:
            conv.hide()
        else:
            conv.show()
        return conv


    def getGroupConversation(self,group,Class=GroupConversation,stayHidden=0):
        """
        For the given group object, returns the group conversation window or
        creates and returns a new group conversation window if it doesn't exist

        @type group: L{Group<interfaces.IGroup>}
        @type Class: L{Conversation<interfaces.IConversation>} class
        @type stayHidden: boolean

        @returntype: L{GroupConversation<interfaces.IGroupConversation>}
        """
        conv = self.groupConversations.get(group)
        if not conv:
            conv = Class(group, self)
            self.groupConversations[group] = conv
        if stayHidden:
            conv.hide()
        else:
            conv.show()
        return conv


    def getPerson(self, name, client):
        """
        For the given name and account client, returns the instance of the
        AbstractPerson subclass, or creates and returns a new AbstractPerson
        subclass of the type Class

        @type name: string
        @type client: L{Client<interfaces.IClient>}

        @returntype: L{Person<interfaces.IPerson>}
        """
        account = client.account
        p = self.persons.get((name, account))
        if not p:
            p = account.getPerson(name)
            self.persons[name, account] = p
        return p


    def getGroup(self, name, client):
        """
        For the given name and account client, returns the instance of the
        AbstractGroup subclass, or creates and returns a new AbstractGroup
        subclass of the type Class

        @type name: string
        @type client: L{Client<interfaces.IClient>}

        @returntype: L{Group<interfaces.IGroup>}
        """
        # I accept 'client' instead of 'account' in my signature for
        # backwards compatibility.  (Groups changed to be Account-oriented
        # in CVS revision 1.8.)
        account = client.account
        g = self.groups.get((name, account))
        if not g:
            g = account.getGroup(name)
            self.groups[name, account] = g
        return g


    def contactChangedNick(self, person, newnick):
        """
        For the given C{person}, change the C{person}'s C{name} to C{newnick}
        and tell the contact list and any conversation windows with that
        C{person} to change as well.

        @type person: L{Person<interfaces.IPerson>}
        @param person: The person whose nickname will get changed.

        @type newnick: C{str}
        @param newnick: The new C{name} C{person} will take.
        """
        oldnick = person.name
        if self.persons.has_key((oldnick, person.account)):
            conv = self.conversations.get(person)
            if conv:
                conv.contactChangedNick(person, newnick)
            self.contactsList.contactChangedNick(person, newnick)
            del self.persons[oldnick, person.account]
            person.name = newnick
            self.persons[person.name, person.account] = person
