class ContactsList:
    """A GUI object that displays a contacts list"""
    def __init__(self, chatui):
        """ContactsList(ChatUI:chatui)"""
        self.chat = chatui
        
    def setContactStatus(self, person):
        """setContactStatus(basesupport.AbstractPerson:person) : None
        Inform the user when a person's status has changed."""


class ConversationWindow:
    """A GUI window of a conversation with a specific person"""
    def __init__(self, person):
        """ConversationWindow(basesupport.AbstractPerson:person)"""
        self.person = person
    
    def sendText(self, text):
        """sendText(string:text) : None|twisted.internet.defer.Deferred
        Sends text to the person with whom the user is conversing"""

    def showMessage(self, text, metadata=None):
        """showMessage(string:text, [dict:metadata]) : None
        Displays to the user a message sent from the person with whom the
        user is conversing"""


class GroupConversationWindow:
    """A GUI window of a conversation witha  group of people"""
    def __init__(self, group):
        """GroupConversationWindow(basesupport.AbstractGroup:group)"""
        self.group = group
    
    def sendText(self, text):
        """sendText(string:text) : None|twisted.internet.defer.Deferred
        Sends text to the group"""

    def showGroupMessage(self, sender, text, metadata=None):
        """showGroupMessage(string:sender, string:text, [dict:metadata]) : None
        Displays to the user a message sent to this group from the given sender
        """

    def setGroupMembers(self, members):
        """setGroupMembers(list{basesupport.AbstractPerson}:members) : None
        Sets the list of members in the group and displays it to the user"""

    def setTopic(self, topic, author):
        """setTopic(string:topic, string:author) : None
        Displays the topic (from the server) for the group conversation window
        """

    def memberJoined(self, member):
        """memberJoined(string:member) : None
        Adds the given member to the list of members in the group conversation
        and displays this to the user"""

    def memberChangedNick(self, oldnick, newnick):
        """memberChangedNick(string:oldnick, string:newnick) : None
        Changes the oldnick in the list of members to newnick and displays this
        change to the user"""

    def memberLeft(self, member):
        """memberLeft(string:member) : None
        Deletes the given member from the list of members in the group
        conversation and displays the change to the user"""


class ChatUI:
    """A GUI chat client"""
    def registerAccountClient(self, account):
        """registerAccountClient(basesupport.AbstractAccount:account) : None
        Notifies user that an account has been signed on to."""

    def unregisterAccountClient(self, account):
        """unregisterAccountClient(basesupport.AbstractAccount:account) : None
        Notifies user that an account has been signed off or disconnected
        from"""

    def getContactsList(self):
        """getContactsList() : ContactsList"""

    def getConversation(self, person, stayHidden=0):
        """getConversation(basesupport.AbstractPerson:person,
                           [boolean:stayHidden]) : ConversationWindow
        For the given person object, returns the conversation window or creates
        and returns a new conversation window if one does not exist."""
      
    def getGroupConversation(self, group, stayHidden=0):
        """getGroupConversation(basesupport.AbstractGroup:group,
                                [boolean:stayHidden]) : GroupConversationWindow
        For the given group object, returns the group conversation window or
        creates and returns a new group conversation window if it doesn't exist
        """

    def getPerson(self, name, account, Class):
        """getPerson(string:name, basesupport.AbstractAccount:account,
                     {basesupport.AbstractPerson subclass}:Class)
             : basesupport.AbstractPerson
        For the given name and account, returns the instance of the
        AbstractPerson subclass, or creates and returns a new AbstractPerson
        subclass of the type Class"""

    def getGroup(self, name, account, Class):
        """getGroup(string:name, basesupport.AbstractAccount:account,
                    {basesupport.AbstractGroup subclass}:Class)
             : basesupport.AbstractGroup
        For the given name and account, returns the instance of the
        AbstractGroup subclass, or creates and returns a new AbstractGroup
        subclass of the type Class"""

