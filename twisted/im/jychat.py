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

    def contactChangedNick(self, person, newnick):
        ContactsList.contactChangedNick(self, person, newnick)
        self.update()

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
    def __init__(self, person, chatui):
        """ConversationWindow(basesupport.AbstractPerson:person)"""
        Conversation.__init__(self, person, chatui)
        self.mainframe = JFrame("Conversation with "+person.name)
        self.display = JTextArea()
        self.display.setColumns(100)
        self.display.setRows(15)
        self.display.setEditable(0)
        self.display.setLineWrap(1)
        self.typepad = JTextField()
        self.buildpane()
        self.lentext = 0

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
        self.displayText("\n"+self.person.client.name+": "+text)
        Conversation.sendText(self, text)

    def showMessage(self, text, metadata=None):
        self.displayText("\n"+self.person.name+": "+text)

    def contactChangedNick(self, person, newnick):
        Conversation.contactChangedNick(self, person, newnick)
        self.mainframe.setTitle("Conversation with "+newnick)

    #GUI code
    def displayText(self, text):
        self.lentext = self.lentext + len(text)
        self.display.append(text)
        self.display.setCaretPosition(self.lentext)

    #actionlisteners
    def hidewindow(self, ae):
        self.hide()

    def send(self, ae):
        text = self.typepad.getText()
        self.typepad.setText("")
        if text != "" and text != None:
            self.sendText(text)


class GroupConversationWindow(GroupConversation):
    """A GUI window of a conversation witha  group of people"""
    def __init__(self, group, chatui):
        GroupConversation.__init__(self, group, chatui)
        self.mainframe = JFrame(self.group.name)
        self.headers = ["Member"]
        self.memberdata = UneditableTableModel([], self.headers)
        self.display = JTextArea()
        self.display.setColumns(100)
        self.display.setRows(15)
        self.display.setEditable(0)
        self.display.setLineWrap(1)
        self.typepad = JTextField()
        self.buildpane()
        self.lentext = 0
            
    def show(self):
        self.mainframe.pack()
        self.mainframe.show()

    def hide(self):
        self.mainframe.hide()
    
    def showGroupMessage(self, sender, text, metadata=None):
        self.displayText(sender + ": " + text)
    
    def setGroupMembers(self, members):
        GroupConversation.setGroupMembers(self, members)
        self.updatelist()
        
    def setTopic(self, topic, author):
        topictext = "Topic: " + topic + ", set by " + author
        self.mainframe.setTitle(self.group.name + ": " + topictext)
        self.displayText(topictext)

    def memberJoined(self, member):
        GroupConversation.memberJoined(self, member)
        self.updatelist()

    def memberChangedNick(self, oldnick, newnick):
        GroupConversation.memberChangedNick(self, oldnick, newnick)
        self.updatelist()

    def memberLeft(self, member):
        GroupConversation.memberLeft(self, member)
        self.updatelist()

    #GUI code
    def buildpane(self):
        buttons = JPanel(doublebuffered)
        buttons.add(actionWidget(JButton("Hide"), self.hidewindow))

        memberpane = JTable(self.memberdata)
        memberframe = JScrollPane(memberpane)

        chat = JPanel(doublebuffered)
        chat.setLayout(BoxLayout(chat, BoxLayout.Y_AXIS))
        chat.add(JScrollPane(self.display))
        chat.add(actionWidget(self.typepad, self.send))
        chat.add(buttons)

        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.X_AXIS))
        mainpane.add(chat)
        mainpane.add(memberframe)
        
    def displayText(self, text):
        self.lentext = self.lentext + len(text)
        self.display.append(text)
        self.display.setCaretPosition(self.lentext)

    def updatelist(self):
        self.memberdata.setDataVector([self.members], self.headers)

    #actionListener
    def send(self, ae):
        text = self.typepad.getText()
        self.typepad.setText("")
        if text != "" and text != None:
            GroupConversation.sendText(self, text)

    def hidewindow(self, ae):
        self.hide()

class JyChatUI(ChatUI):
    def __init__(self):
        ChatUI.__init__(self)
        self.contactsList = ContactsListGUI(self)

    def getConversation(self, person, stayHidden=0):
        return ChatUI.getGroupConversation(self, person, ConversationWindow,
                                            stayHidden)

    def getGroupConversation(self, group, stayHidden=0):
        return ChatUI.getGroupConversation(self, group,
                                            GroupConversationWindow,
                                            stayHidden)
    
