from twisted.im.locals import OFFLINE, ONLINE, AWAY

class ContactsList:
    """A GUI object that displays a contacts list"""
    def __init__(self, chatui):
        """ContactsList(ChatUI:chatui)"""
        self.chatui = chatui
        self.contacts = {}
        self.onlineContacts = {}
        self.clients = []
        
    def setContactStatus(self, person):
        """setContactStatus(basesupport.AbstractPerson:person) : None
        Inform the user when a person's status has changed."""
        if not self.contacts.has_key(person.name):
            self.contacts[person.name] = person
        if not self.onlineContacts.has_key(person.name) and \
            (person.status == ONLINE or person.status == AWAY):
            self.onlineContacts[person.name] = person
        if self.onlineContacts.has_key(person.name) and \
           person.status == OFFLINE:
            del self.onlineContacts[person.name]

    def registerAccountClient(self, client):
        """registerAccountClient(basesupport.AbstractClientMixin:client) : None
        Notifies user that an account client has been signed on to."""
        if not client in self.clients:
            self.clients.append(client)

    def unregisterAccountClient(self, client):
        """unregisterAccountClient(basesupport.AbstractClientMixin:client) :
                   None
        Notifies user that an account client has been signed off or 
        disconnected from"""
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
        """ConversationWindow(basesupport.AbstractPerson:person,
                              ChatUI:chatui)
        """
        self.chatui = chatui
        self.person = person
    
    def show(self):
        """show() : None
        Displays the ConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")

    def hide(self):
        """hide() : None
        Hides the ConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")

    def sendText(self, text):
        """sendText(string:text) : None|twisted.internet.defer.Deferred
        Sends text to the person with whom the user is conversing"""
        self.person.sendMessage(text, None)

    def showMessage(self, text, metadata=None):
        """showMessage(string:text, [dict:metadata]) : None
        Displays to the user a message sent from the person with whom the
        user is conversing"""
        raise NotImplementedError("Subclasses must implement this method")

    def contactChangedNick(self, person, newnick):
        """contactChangedNick(basesupport.AbstractPerson:person,
                              string:newnick) : None
        For the given person, changes the person's name to newnick, and
        tells the user that the nick has changed"""
        self.person.name = newnick


class GroupConversation:
    """A GUI window of a conversation with a group of people"""
    def __init__(self, group, chatui):
        """GroupConversationWindow(basesupport.AbstractGroup:group,
                                   ChatUI:chatui)
        """
        self.chatui = chatui
        self.group = group
        self.members = []

    def show(self):
        """show() : None
        Displays the GroupConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")

    def hide(self):
        """hide() : None
        Hides the GroupConversationWindow"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def sendText(self, text):
        """sendText(string:text) : None|twisted.internet.defer.Deferred
        Sends text to the group"""
        self.group.sendGroupMessage(text, None)
    
    def showGroupMessage(self, sender, text, metadata=None):
        """showGroupMessage(string:sender, string:text, [dict:metadata]) : None
        Displays to the user a message sent to this group from the given sender
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def setGroupMembers(self, members):
        """setGroupMembers(list{string}:members) : None
        Sets the list of members in the group and displays it to the user"""
        self.members = members

    def setTopic(self, topic, author):
        """setTopic(string:topic, string:author) : None
        Displays the topic (from the server) for the group conversation window
        """
        raise NotImplementedError("Subclasses must implement this method")

    def memberJoined(self, member):
        """memberJoined(string:member) : None
        Adds the given member to the list of members in the group conversation
        and displays this to the user"""
        if not member in self.members:
            self.members.append(member)

    def memberChangedNick(self, oldnick, newnick):
        """memberChangedNick(string:oldnick, string:newnick) : None
        Changes the oldnick in the list of members to newnick and displays this
        change to the user"""
        if oldnick in self.members:
            self.members.remove(oldnick)
            self.members.append(newnick)
            #self.chatui.contactChangedNick(oldnick, newnick)

    def memberLeft(self, member):
        """memberLeft(string:member) : None
        Deletes the given member from the list of members in the group
        conversation and displays the change to the user"""
        if member in self.members:
            self.members.remove(member)


class ChatUI:
    """A GUI chat client"""
    def __init__(self):
        self.conversations = {}      # cache of all direct windows
        self.groupConversations = {} # cache of all group windows
        self.persons = {}            # keys are (name, client)
        self.groups = {}             # cache of all groups
        self.onlineClients = []      # list of message sources currently online
        self.contactsList = ContactsList(self)
    
    def registerAccountClient(self, client):
        """registerAccountClient(basesupport.AbstractClientMixin:client) : None
        Notifies user that an account has been signed on to."""
        print "signing onto", client.accountName
        self.onlineClients.append(client)
        self.contactsList.registerAccountClient(client)

    def unregisterAccountClient(self, client):
        """unregisterAccountClient(basesupport.AbstractClientMixin:client) : None
        Notifies user that an account has been signed off or disconnected
        from"""
        print "signing off from", client.accountName
        self.onlineClients.remove(client)
        self.contactsList.unregisterAccountClient(client)

    def getContactsList(self):
        """getContactsList() : ContactsList"""
        return self.contactsList

    def getConversation(self, person, Class=Conversation, stayHidden=0):
        """getConversation(basesupport.AbstractPerson:person,
                           [{Conversation subclass}Class], 
                           [boolean:stayHidden]) : Class
        For the given person object, returns the conversation window or creates
        and returns a new conversation window if one does not exist."""
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
        """getGroupConversation(basesupport.AbstractGroup:group,
                                [{GroupConversation subclass}Class],
                                [boolean:stayHidden]) : Class
        For the given group object, returns the group conversation window or
        creates and returns a new group conversation window if it doesn't exist
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

    def getPerson(self, name, client, Class):
        """getPerson(string:name, basesupport.AbstractClientMixin:client,
                     {basesupport.AbstractPerson subclass}:Class)
             : basesupport.AbstractPerson
        For the given name and account client, returns the instance of the
        AbstractPerson subclass, or creates and returns a new AbstractPerson
        subclass of the type Class"""
        p = self.persons.get((name, client))
        if not p:
            p = Class(name, client, self)
            self.persons[name, client] = p
        return p

    def getGroup(self, name, client, Class):
        """getGroup(string:name, basesupport.AbstractClientMixin:client,
                    {basesupport.AbstractGroup subclass}:Class)
             : basesupport.AbstractGroup
        For the given name and account client, returns the instance of the
        AbstractGroup subclass, or creates and returns a new AbstractGroup
        subclass of the type Class"""
        g = self.groups.get((name, client))
        if not g:
            g = Class(name, client, self)
            self.groups[name, client] = g
        return g

    def contactChangedNick(self, oldnick, newnick):
        """contactChangedNick(string:oldnick, string:newnick) : None
        For the given person, changes the person's name to newnick, and
        tells the contact list and any conversation windows with that person
        to change as well."""
        if self.persons.has_key((person.name, person.client)):
            conv = self.conversations.get(person)
            if conv:
                conv.contactChangedNick(person, newnick)

            self.contactsList.contactChangedNick(person, newnick)
                
            del self.persons[person.name, person.client]
            person.name = newnick
            self.persons[person.name, person.client] = person
