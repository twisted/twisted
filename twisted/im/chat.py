import string

import gtk

from twisted.im.locals import GLADE_FILE, autoConnectMethods, InputOutputWindow, openGlade
from twisted.im.account import onlineAccounts

class GroupJoinWindow:
    def __init__(self):
        self.xml = openGlade(GLADE_FILE, root="JoinGroupWindow")
        self.widget = self.xml.get_widget("JoinGroupWindow")
        autoConnectMethods(self)
        om = self.xml.get_widget("AccountSelector")
        m = gtk.GtkMenu()
        om.set_menu(m)
        activ = 0
        for acct in onlineAccounts:
            print 'adding account to menu:',acct.accountName
            i = gtk.GtkMenuItem(acct.accountName)
            m.append(i)
            i.connect('activate', self.on_AccountSelectorMenu_activate, acct)
        if onlineAccounts:
            self.currentAccount = onlineAccounts[0]
        self.widget.show_all()

    def on_AccountSelectorMenu_activate(self, m, acct):
        self.currentAccount = acct

    def on_GroupJoinButton_clicked(self, b):
        name = self.xml.get_widget("GroupNameEntry").get_text()
        self.currentAccount.joinGroup(name)
        self.widget.destroy()


class ContactsList:
    def __init__(self):
        self.xml = openGlade(GLADE_FILE, root="ContactsWidget")
        self.widget = self.xml.get_widget("ContactsWidget")
        self.people = []
        self.onlinePeople = []
        self.countOnline = 0
        autoConnectMethods(self)
        self.selectedPerson = None
        self.xml.get_widget("OnlineCount").set_text("Online: 0")

    def setContactStatus(self, person):
        if person not in self.people:
            self.people.append(person)
        self.refreshContactsLists()

    def on_OnlineContactsList_select_row(self, w, row, column, event):
        self.selectedPerson = self.onlinePeople[row]

    def on_PlainSendIM_clicked(self, b):
        if self.selectedPerson:
            c = getConversation(self.selectedPerson)

    def on_PlainJoinChat_clicked(self, b):
        GroupJoinWindow()

    def refreshContactsLists(self):
        # HIDEOUSLY inefficient
        online = self.xml.get_widget("OnlineContactsList")
        offline = self.xml.get_widget("OfflineContactsList")
        online.clear()
        offline.clear()
        self.countOnline = 0
        self.onlinePeople = []
        self.people.sort(lambda x, y: cmp(x.name, y.name))
        for person in self.people:
            if person.isOnline():
                self.onlinePeople.append(person)
                online.append([person.name, person.getStatus()])
                self.countOnline = self.countOnline + 1
            offline.append([person.name, person.account.accountName, 'Aliasing Not Implemented', 'Groups Not Implemented'])
        self.xml.get_widget("OnlineCount").set_text("Online: %d" % self.countOnline)



class Conversation(InputOutputWindow):
    """GUI representation of a conversation.
    """
    def __init__(self, person):
        InputOutputWindow.__init__(self,
                                   "ConversationWidget",
                                   "ConversationMessageEntry",
                                   "ConversationOutput")
        self.person = person

    def getTitle(self):
        return "Conversation - " + self.person.name

    def sendText(self, text):
        metadata = None
        if text[:4] == "/me ":
            text = text[4:]
            metadata = {"style": "emote"}
        self.person.sendMessage(text, metadata).addCallback(self._cbTextSent, text, metadata)

    def showMessage(self, text, metadata=None):
        text = string.replace(text, '\n', '\n\t')
        msg = "<%s> %s\n" % (self.person.name, text)
        if metadata:
            if metadata.get("style", None) == "emote":
                msg = "* %s %s\n" % (self.person.name, text)
        self.output.insert_defaults(msg)

    def _cbTextSent(self, result, text, metadata=None):
        print 'result:',result
        text = string.replace(text, '\n', '\n\t')
        msg = "<%s> %s\n" % (self.person.account.name, text)
        if metadata:
            if metadata.get("style", None) == "emote":
                msg = "* %s %s\n" % (self.person.account.name, text)
        self.output.insert_defaults(msg)

class GroupConversation(InputOutputWindow):
    def __init__(self, group):
        InputOutputWindow.__init__(self,
                                   "GroupChatBox",
                                   "GroupInput",
                                   "GroupOutput")
        self.group = group
        self.members = []
        self.membersHidden = 0
        self.xml.get_widget("NickLabel").set_text(self.group.account.name)

    def hidden(self, w):
        InputOutputWindow.hidden(self, w)
        self.group.leave()

    def getTitle(self):
        return "Group Conversation - " + self.group.name

    def sendText(self, text):
        metadata = None
        if text[:4] == "/me ":
            text = text[4:]
            metadata = {"style": "emote"}
        self.group.sendGroupMessage(text, metadata).addCallback(self._cbTextSent, text, metadata=metadata)

    def showGroupMessage(self, sender, text, metadata=None):
        text = string.replace(text, '\n', '\n\t')
        msg = "<%s> %s\n" % (sender, text)
        if metadata:
            if metadata.get("style", None) == "emote":
                msg = "* %s %s\n" % (sender, text)
        self.output.insert_defaults(msg)

    def setGroupMembers(self, members):
        self.members = members
        self.refreshMemberList()

    def setTopic(self, topic, author):
        self.xml.get_widget("TopicEntry").set_text(topic)
        self.xml.get_widget("AuthorLabel").set_text(author)

    def memberJoined(self, member):
        self.members.append(member)
        self.output.insert_defaults("> %s joined <\n" % member)
        self.refreshMemberList()

    def memberLeft(self, member):
        self.members.remove(member)
        self.output.insert_defaults("> %s left <\n" % member)
        self.refreshMemberList()

    def refreshMemberList(self):
        pl = self.xml.get_widget("ParticipantList")
        pl.clear()
        for member in self.members:
            pl.append([member])

    def on_HideButton_clicked(self, b):
        self.membersHidden = not self.membersHidden
        self.xml.get_widget("GroupHPaned").set_position(self.membersHidden and -1 or 20000)

    def on_LeaveButton_clicked(self, b):
        self.win.destroy()
        self.group.leave()

    def on_AddContactButton_clicked(self, b):
        lw = self.xml.get_widget("ParticipantList")

        if lw.selection:
            self.group.account.perspective.callRemote('addContact', self.members[lw.selection[0]])

    def on_TopicEntry_activate(self, e):
        print "ACTIVATING TOPIC!!"
        self.group.setTopic(e.get_text())


    def _cbTextSent(self, result, text, metadata=None):
        print text
        text = string.replace(text, '\n', '\n\t')
        msg = "<%s> %s\n" % (self.group.account.name, text)
        if metadata:
            if metadata.get("style", None) == "emote":
                msg = "* %s %s\n" % (self.group.account.name, text)
        self.output.insert_defaults(msg)

# IM-GUI Utility functions

theContactsList = None

def getContactsList():
    global theContactsList
    if not theContactsList:
        theContactsList = ContactsList()
        w = gtk.GtkWindow(gtk.WINDOW_TOPLEVEL)
        w.set_title("Contacts List")
        w.add(theContactsList.widget)
        w.show_all()
    return theContactsList

conversations = {}                      # cache of all direct windows

def getConversation(person):
    conv = conversations.get(person)
    if not conv:
        conv = Conversation(person)
        conversations[person] = conv
    conv.show()
    return conv

groupConversations = {}                 # cache of all group windows

def getGroupConversation(group, stayHidden=0):
    conv = groupConversations.get(group)
    if not conv:
        conv = GroupConversation(group)
        groupConversations[group] = conv
    if not stayHidden:
        conv.show()
    return conv

personCache = {}                        # keys are (name, account)

def getPerson(name, account, Class):
    p = personCache.get((name, account))
    if not p:
        p = Class(name, account)
        personCache[name, account] = p
    return p

groupCache = {}                         # cache of all groups

def getGroup(name, account, Class):
    g = groupCache.get((name, account))
    if not g:
        g = Class(name, account)
        groupCache[name, account] = g
    return g





### --- End IM-Gui utility functions


