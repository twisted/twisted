from twisted.im.basechat import ContactsList, Conversation, GroupConversation,\
     ChatUI
from twisted.im.locals import OFFLINE, ONLINE, AWAY

from java.awt import GridLayout, FlowLayout, BorderLayout, Container
import sys
from java.awt.event import ActionListener
from javax.swing import JTextField, JPasswordField, JComboBox, JPanel, JLabel,\
     JTextArea, JFrame, JButton, BoxLayout, JTable, JScrollPane, \
     ListSelectionModel
from javax.swing.table import DefaultTableModel

doublebuffered = 0

class _Listener(ActionListener):
    def __init__(self, callable):
        self.callable = callable
    def actionPerformed(self, ae):
        self.callable(ae)

def actionWidget(widget, callable):
    widget.addActionListener(_Listener(callable))
    return widget

class UneditableTableModel(DefaultTableModel):
    def isCellEditable(self, x, y):
        return 0

class _AccountAdder:
    def __init__(self, contactslist):
        self.contactslist = contactslist
        self.mainframe = JFrame("Add New Contact")
        self.account = JComboBox(self.contactslist.clientsByName.keys())
        self.contactname = JTextField()
        self.buildpane()

    def buildpane(self):
        buttons = JPanel()
        buttons.add(actionWidget(JButton("OK"), self.add))
        buttons.add(actionWidget(JButton("Cancel"), self.cancel))

        acct = JPanel(GridLayout(1, 2), doublebuffered)
        acct.add(JLabel("Account"))
        acct.add(self.account)

        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.Y_AXIS))
        mainpane.add(self.contactname)
        mainpane.add(acct)
        mainpane.add(buttons)
        self.mainframe.pack()
        self.mainframe.show()

    #action listeners
    def add(self, ae):
        acct = self.contactslist.clientsByName[self.account.getSelectedItem()]
        acct.addContact(self.contactname.getText())
        self.mainframe.dispose()
    
    def cancel(self, ae):
        self.mainframe.dispose()

class ContactsListGUI(ContactsList):
    """A GUI object that displays a contacts list"""
    def __init__(self, chatui):
        ContactsList.__init__(self, chatui)
        self.clientsByName = {}
        self.mainframe = JFrame("Contacts List")
        self.headers = ["Contact", "Status", "Idle", "Account"]
        self.data = UneditableTableModel([], self.headers)
        self.table = JTable(self.data)
        self.table.setColumnSelectionAllowed(0)   #cannot select columns
        self.table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)

        self.buildpane()
        self.mainframe.pack()
        self.mainframe.show()
    
    def setContactStatus(self, person):
        ContactsList.setContactStatus(self, person)
        self.update()

    def registerAccountClient(self, client):
        ContactsList.registerAccountClient(self, client)
        if not client.accountName in self.clientsByName.keys():
            self.clientsByName[client.accountName] = client

    def unregisterAccount(self, client):
        ContactsList.unregisterAccountClient(self, client)
        if client.accountName in self.clientsByName.keys():
            del self.clientsByName[client.accountName]

    #GUI code
    def buildpane(self):
        buttons = JPanel(FlowLayout(), doublebuffered)
        buttons.add(actionWidget(JButton("Send Message"), self.message))
        buttons.add(actionWidget(JButton("Add Contact"), self.addContact))
        #buttons.add(actionWidget(JButton("Quit"), self.quit))

        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.Y_AXIS))
        mainpane.add(JScrollPane(self.table))
        mainpane.add(buttons)
        self.update()
    
    def update(self):
        contactdata = []
        for contact in self.onlineContacts.values():
            if contact.status == AWAY:
                stat = "(away)"
            else:
                stat = "(active)"
            contactdata.append([contact.name, stat, contact.getIdleTime(),
                                contact.client.accountName])
        self.data.setDataVector(contactdata, self.headers)

    #callable actionlisteners
    def message(self, ae):
        row = self.table.getSelectedRow()
        if row < 0:
            print "Trying to send IM to person, but no person selected"
        else:
            person = self.onlineContacts[self.data.getValueAt(row, 0)]
            self.chat.getConversation(person)
    
    def addContact(self, ae):
        _AccountAdder(self)
        
    def quit(self, ae):
        sys.exit()


class ConversationWindow(Conversation):
    """A GUI window of a conversation with a specific person"""
    def __init__(self, person):
        """ConversationWindow(basesupport.AbstractPerson:person)"""
        self.person = person
        self.mainframe = JFrame("Conversation with "+person.name)
        self.display = JTextArea("Starting conversation with "+person.name)
        self.display.setColumns(50)
        self.display.setRows(10)
        self.display.setEditable(0)
        self.display.setLineWrap(1)
        self.typepad = JTextField()
        self.buildpane()

    def buildpane(self):
        buttons = JPanel(doublebuffered)
        buttons.add(actionWidget(JButton("Send"), self.send))
        buttons.add(actionWidget(JButton("Hide"), self.hidewindow))

        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.Y_AXIS))
        mainpane.add(JScrollPane(self.display))
        mainpane.add(actionWidget(self.typepad, self.send))
        mainpane.add(buttons)
    
    def show(self):
        self.mainframe.pack()
        self.mainframe.show()

    def hide(self):
        self.mainframe.hide()

    def sendText(self, text):
        self.display.append("\n"+self.person.client.name+": "+text)
        self.person.sendMessage(text, None)

    def showMessage(self, text, metadata=None):
        self.display.append("\n"+self.person.name+": "+text)

    #actionlisteners
    def hidewindow(self, ae):
        self.hide()

    def send(self, ae):
        text = self.typepad.getText()
        if text != "" and text != None:
            self.sendText(text)


class GroupConversationWindow(GroupConversation):
    """A GUI window of a conversation witha  group of people"""
    def __init__(self, group):
        """GroupConversationWindow(basesupport.AbstractGroup:group)"""
        self.group = group
    
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
        raise NotImplementedError("Subclasses must implement this method")
    
    def showGroupMessage(self, sender, text, metadata=None):
        """showGroupMessage(string:sender, string:text, [dict:metadata]) : None
        Displays to the user a message sent to this group from the given sender
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def setGroupMembers(self, members):
        """setGroupMembers(list{basesupport.AbstractPerson}:members) : None
        Sets the list of members in the group and displays it to the user"""
        raise NotImplementedError("Subclasses must implement this method")

    def setTopic(self, topic, author):
        """setTopic(string:topic, string:author) : None
        Displays the topic (from the server) for the group conversation window
        """
        raise NotImplementedError("Subclasses must implement this method")

    def memberJoined(self, member):
        """memberJoined(string:member) : None
        Adds the given member to the list of members in the group conversation
        and displays this to the user"""
        raise NotImplementedError("Subclasses must implement this method")

    def memberChangedNick(self, oldnick, newnick):
        """memberChangedNick(string:oldnick, string:newnick) : None
        Changes the oldnick in the list of members to newnick and displays this
        change to the user"""
        raise NotImplementedError("Subclasses must implement this method")

    def memberLeft(self, member):
        """memberLeft(string:member) : None
        Deletes the given member from the list of members in the group
        conversation and displays the change to the user"""
        raise NotImplementedError("Subclasses must implement this method")

class JyChatUI(ChatUI):
    def __init__(self):
        ChatUI.__init__(self)
        self.contactsList = ContactsListGUI(self)

    def getConversation(self, person, stayHidden=0):
        return ChatUI._getGroupConversation(self, person, ConversationWindow,
                                            stayHidden)

    def getGroupConversation(self, group, stayHidden=0):
        return ChatUI._getGroupConversation(self, group,
                                            GroupConversationWindow,
                                            stayHidden)
    
