# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

import string
import time

import gtk

from twisted.im.gtkcommon import GLADE_FILE, autoConnectMethods, InputOutputWindow, openGlade

class ContactsList:
    def __init__(self, chatui):
        self.xml = openGlade(GLADE_FILE, root="ContactsWidget")
        self.widget = self.xml.get_widget("ContactsWidget")
        self.people = []
        self.onlinePeople = []
        self.countOnline = 0
        autoConnectMethods(self)
        self.selectedPerson = None
        self.xml.get_widget("OnlineCount").set_text("Online: 0")
        self.chat = chatui

        # Construct Menu for Account Selection
        self.optionMenu = self.xml.get_widget("AccountsListPopup")
        self.accountMenuItems = []
        self.currentAccount = None


    def registerAccountClient(self, account):
        print 'registering account client', self, account
        self.accountMenuItems.append(account)
        self._updateAccountMenu()

    def _updateAccountMenu(self):
        # This seems to be necessary -- I don't understand gtk's handling of
        # GtkOptionMenus
        print 'updating account menu', self.accountMenuItems
        self.accountMenu = gtk.GtkMenu()
        for account in self.accountMenuItems:
            i = gtk.GtkMenuItem(account.accountName)
            i.connect('activate', self.on_AccountsListPopup_activate, account)
            self.accountMenu.append(i)
        if self.accountMenuItems:
            print "setting default account to", self.accountMenuItems[0]
            self.currentAccount = self.accountMenuItems[0]
        self.accountMenu.show_all()
        self.optionMenu.set_menu(self.accountMenu)

    def on_AccountsListPopup_activate(self, w, account):
        print 'setting current account', account
        self.currentAccount = account

    def on_AddContactButton_clicked(self, b):
        self.currentAccount.addContact(
            self.xml.get_widget("ContactNameEntry").get_text())
        
    def unregisterAccountClient(self,account):
        print 'unregistering account client', self, account
        self.accountMenuItems.remove(account)
        self._updateAccountMenu()

    def setContactStatus(self, person):
        if person not in self.people:
            self.people.append(person)
        self.refreshContactsLists()

    def on_OnlineContactsTree_select_row(self, w, row, column, event):
        self.selectedPerson = self.onlinePeople[row]
        entry = self.xml.get_widget("ContactNameEntry")
        entry.set_text(self.selectedPerson.name)
        self.currentAccount = self.selectedPerson.client
        idx = self.accountMenuItems.index(self.currentAccount)
        self.accountMenu.set_active(idx)
        self.optionMenu.remove_menu()
        self.optionMenu.set_menu(self.accountMenu)

    def on_PlainSendIM_clicked(self, b):
        self.chat.getConversation(
            self.currentAccount.getPerson(
            self.xml.get_widget("ContactNameEntry").get_text()))
##         if self.selectedPerson:
##             c = self.chat.getConversation(self.selectedPerson)

    def on_PlainJoinChat_clicked(self, b):
        ## GroupJoinWindow(self.chat)
        name = self.xml.get_widget("ContactNameEntry").get_text()
        self.currentAccount.joinGroup(name)

    def refreshContactsLists(self):
        # HIDEOUSLY inefficient
        online = self.xml.get_widget("OnlineContactsTree")
        offline = self.xml.get_widget("OfflineContactsList")
        online.freeze()
        offline.freeze()
        online.clear()
        offline.clear()
        self.countOnline = 0
        self.onlinePeople = []
        self.people.sort(lambda x, y: cmp(x.name, y.name))
        for person in self.people:
            if person.isOnline():
                self.onlinePeople.append(person)
                online.append([person.name, person.getStatus(),
                               person.getIdleTime(), person.client.accountName])
                self.countOnline = self.countOnline + 1
            offline.append([person.name, person.client.accountName,
                            'Aliasing Not Implemented', 'Groups Not Implemented'])
        self.xml.get_widget("OnlineCount").set_text("Online: %d" % self.countOnline)
        online.thaw()
        offline.thaw()



def colorhash(name):
    h = hash(name)
    l = [0x5555ff,
         0x55aa55,
         0x55aaff,
         0xff5555,
         0xff55ff,
         0xffaa55]
    index = l[h % len(l)]
    return '%06.x' % (abs(hash(name)) & index)


def _msgDisplay(output, name, text, color, isEmote):
    text = string.replace(text, '\n', '\n\t')
    ins = output.insert
    ins(None, color, None, "[ %s ] " % time.strftime("%H:%M:%S"))
    if isEmote:
        ins(None, color, None, "* %s " % name)
        ins(None, None, None, "%s\n" % text)
    else:
        ins(None, color, None, "<%s> " % name)
        ins(None, None, None, "%s\n" % text)


class Conversation(InputOutputWindow):
    """GUI representation of a conversation.
    """
    def __init__(self, person):
        InputOutputWindow.__init__(self,
                                   "ConversationWidget",
                                   "ConversationMessageEntry",
                                   "ConversationOutput")
        self.person = person
        alloc_color = self.output.get_colormap().alloc
        self.personColor = alloc_color("#%s" % colorhash(person.name))
        self.myColor = alloc_color("#0000ff")
        print "allocated my color %s and person color %s" % (
            self.myColor, self.personColor)

    def getTitle(self):
        return "Conversation - %s (%s)" % (self.person.name, self.person.client.accountName)

    def sendText(self, text):
        metadata = None
        if text[:4] == "/me ":
            text = text[4:]
            metadata = {"style": "emote"}
        self.person.sendMessage(text, metadata).addCallback(self._cbTextSent, text, metadata)

    def showMessage(self, text, metadata=None):
        _msgDisplay(self.output, self.person.name, text, self.personColor,
                    (metadata and metadata.get("style", None) == "emote"))

    def _cbTextSent(self, result, text, metadata=None):
        _msgDisplay(self.output, self.person.client.name, text, self.myColor,
                    (metadata and metadata.get("style", None) == "emote"))

class GroupConversation(InputOutputWindow):
    def __init__(self, group):
        InputOutputWindow.__init__(self,
                                   "GroupChatBox",
                                   "GroupInput",
                                   "GroupOutput")
        self.group = group
        self.members = []
        self.membersHidden = 0
        self._colorcache = {}
        alloc_color = self.output.get_colormap().alloc
        self.myColor = alloc_color("#0000ff")
        self.xml.get_widget("NickLabel").set_text(self.group.client.name)
        participantList = self.xml.get_widget("ParticipantList")
        groupBox = self.xml.get_widget("GroupActionsBox")
        for method in group.getGroupCommands():
            b = gtk.GtkButton(method.__name__)
            b.connect("clicked", self._doGroupAction, method)
            groupBox.add(b)

    def on_ParticipantList_unselect_row(self, w, row, column, event):
        print 'row unselected'
        personBox = self.xml.get_widget("PersonActionsBox")
        for child in personBox.children():
            personBox.remove(child)

    def on_ParticipantList_select_row(self, w, row, column, event):
        self.selectedPerson = self.group.client.getPerson(self.members[row])
        print 'selected', self.selectedPerson
        personBox = self.xml.get_widget("PersonActionsBox")
        personFrame = self.xml.get_widget("PersonFrame")
        # clear out old buttons
        for child in personBox.children():
            personBox.remove(child)
        personFrame.set_label("Person: %s" % self.selectedPerson.name)
        for method in self.selectedPerson.getPersonCommands():
            b = gtk.GtkButton(method.__name__)
            b.connect("clicked", self._doPersonAction, method)
            personBox.add(b)
            b.show()
        for method in self.group.getTargetCommands(self.selectedPerson):
            b = gtk.GtkButton(method.__name__)
            b.connect("clicked", self._doTargetAction, method,
                      self.selectedPerson)
            personBox.add(b)
            b.show()

    def _doGroupAction(self, evt, method):
        method()

    def _doPersonAction(self, evt, method):
        method()

    def _doTargetAction(self, evt, method, person):
        method(person)

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

    def _cacheColorHash(self, name):
        if self._colorcache.has_key(name):
            return self._colorcache[name]
        else:
            alloc_color = self.output.get_colormap().alloc
            c = alloc_color('#%s' % colorhash(name))
            self._colorcache[name] = c
            return c

    def showGroupMessage(self, sender, text, metadata=None):
        _msgDisplay(self.output, sender, text, self._cacheColorHash(sender),
                    (metadata and metadata.get("style", None) == "emote"))

    def _cbTextSent(self, result, text, metadata=None):
        _msgDisplay(self.output, self.group.client.name, text, self.myColor,
                    (metadata and metadata.get("style", None) == "emote"))

    def tabComplete(self, word):
        """InputOutputWindow calls me when tab is pressed."""
        if not word:
            return []
        potentialMatches = []
        for nick in self.members:
            if string.lower(nick[:len(word)]) == string.lower(word):
                potentialMatches.append(nick + ": ") #colon is a nick-specific thing
        return potentialMatches

        
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

    def memberChangedNick(self, member, newnick):
        self.members.remove(member)
        self.members.append(newnick)
        self.output.insert_defaults("> %s becomes %s <\n" % (member, newnick))
        self.refreshMemberList()

    def memberLeft(self, member):
        self.members.remove(member)
        self.output.insert_defaults("> %s left <\n" % member)
        self.refreshMemberList()

    def refreshMemberList(self):
        pl = self.xml.get_widget("ParticipantList")
        pl.freeze()
        pl.clear()
        self.members.sort(lambda x,y: cmp(string.lower(x), string.lower(y)))
        for member in self.members:
            pl.append([member])
        pl.thaw()

        
    def on_HideButton_clicked(self, b):
        self.membersHidden = not self.membersHidden
        self.xml.get_widget("GroupHPaned").set_position(self.membersHidden and -1 or 20000)

    def on_LeaveButton_clicked(self, b):
        self.win.destroy()
        self.group.leave()

    def on_AddContactButton_clicked(self, b):
        lw = self.xml.get_widget("ParticipantList")

        if lw.selection:
            self.group.client.addContact(self.members[lw.selection[0]])

    def on_TopicEntry_activate(self, e):
        print "ACTIVATING TOPIC!!"
        self.group.setTopic(e.get_text())


class GtkChatClientUI:
    # IM-GUI Utility functions
    def __init__(self):
        self.conversations = {}         # cache of all direct windows
        self.groupConversations = {}    # cache of all group windows
        self.personCache = {}           # keys are (name, account)
        self.groupCache = {}            # cache of all groups
        self.theContactsList = None
        self.onlineAccounts = []     # list of message sources currently online
        
    def registerAccountClient(self,account):
        print 'registering account client'
        self.onlineAccounts.append(account)
        self.getContactsList().registerAccountClient(account)

    def unregisterAccountClient(self,account):
        print 'unregistering account client'
        self.onlineAccounts.remove(account)
        self.getContactsList().unregisterAccountClient(account)

    def getContactsList(self):
        if not self.theContactsList:
            self.theContactsList = ContactsList(self)
            w = gtk.GtkWindow(gtk.WINDOW_TOPLEVEL)
            w.set_title("Contacts List")
            w.add(self.theContactsList.widget)
            w.show_all()
        return self.theContactsList

    def getConversation(self, person):
        conv = self.conversations.get(person)
        if not conv:
            conv = Conversation(person)
            self.conversations[person] = conv
        conv.show()
        return conv

    def getGroupConversation(self, group, stayHidden=0):
        conv = self.groupConversations.get(group)
        if not conv:
            conv = GroupConversation(group)
            self.groupConversations[group] = conv
        if not stayHidden:
            conv.show()
        else:
            conv.hide()
        return conv

    def getPerson(self, name, account, Class):
        p = self.personCache.get((name, account))
        if not p:
            p = Class(name, account, self)
            self.personCache[name, account] = p
        return p

    def getGroup(self, name, account, Class):
        g = self.groupCache.get((name, account))
        if not g:
            g = Class(name, account, self)
            self.groupCache[name, account] = g
        return g

    ### --- End IM-Gui utility functions


