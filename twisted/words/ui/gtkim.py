
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


# System Imports
import gtk
import time
from twisted.internet import ingtkernet
ingtkernet.install()

# Twisted Imports
from twisted.spread import pb
from twisted.spread.ui import gtkutil
from twisted.words.ui import im
class Group(pb.RemoteCache):
    """A local cache of a group.
    """

pb.setCopierForClass("twisted.words.service.Group", Group)


class AccountManager(gtk.GtkWindow, gtkutil.ButtonBar):
    def __init__(self, *args, **kw):
        apply(gtk.GtkWindow.__init__, (self,)+args, kw)
        self.accounts = []
        vbox = gtk.GtkVBox(gtk.FALSE, 5)
        vbox.set_border_width(5)
        self.add(vbox)
        titles = ['Username', 'Online', 'Auto-Login', 'Gateway']
        clist = gtk.GtkCList(len(titles), titles)
        clist.signal_connect("select_row", self.rowSelected)
        clist.set_shadow_type(gtk.SHADOW_OUT)
        scrolled = gtk.GtkScrolledWindow(None, None)
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        vbox.pack_start(scrolled, gtk.TRUE, gtk.TRUE, 0)
        scrolled.add(clist)
        hb = gtk.GtkHBox(gtk.FALSE, 0)
        vbox.pack_start(hb, gtk.FALSE, gtk.TRUE, 0)
        self.getButtonList(container=hb)
        self.signal_connect('destroy', gtk.mainquit, None)

    barButtons = ['Add', 'Modify', 'Logon', 'Delete']
    def button_Add(self, btn):
        AddAccount(gtk.WINDOW_TOPLEVEL)

    def button_Modify(self, btn):
        print 'modify clicked!'

    def button_Logon(self, btn):
        print 'logon clicked!'

    def button_Delete(self, btn):
        print 'delete clicked!'

    def rowSelected(self, clist, row, column, event, data):
        print 'hi'

class _AccountInstantiator:
    def __init__(self, this, vb, klas):
        self.this = this
        self.vb = vb
        self.klas = klas

    def activate(self, mitem):
        print 'CHANGIN',mitem
        k = self.klas()
        old = self.this.currentAcct
        if old:
            self.vb.remove(old)
        self.this.currentAcct = k
        self.vb.pack_start(k, padding=2)
        k.show_all()

class AddAccount(gtk.GtkWindow):
    currentAcct = None
    def __init__(self, *args, **kw):
        apply(gtk.GtkWindow.__init__, (self,)+args, kw)
        vb = gtk.GtkVBox()
        hb = gtk.GtkHBox()
        vb.pack_start(hb, expand=gtk.FALSE, fill=gtk.TRUE, padding=2)
        hb.pack_start(gtk.GtkLabel("Account Type:"),
                      expand=gtk.FALSE, fill=gtk.FALSE, padding=2)
        om = gtk.GtkOptionMenu()
        # m = om.get_menu()
        m = gtk.GtkMenu()
        for name, klas in registeredTypes:
            i = gtk.GtkMenuItem(name)
            m.append(i)
            i.connect("activate", _AccountInstantiator(self, vb, klas).activate)
        om.set_menu(m)
        hb.pack_start(om, expand=gtk.TRUE, fill=gtk.TRUE, padding=2)
        self.add(vb)
        self.set_usize(300, 300)
        self.show_all()

class DummyAOLPanel(gtk.GtkFrame):
    def __init__(self):
        gtk.GtkFrame.__init__(self, "AOL Account")
        self.add(gtk.GtkButton("AOL!"))
class DummyIRCPanel(gtk.GtkFrame):
    def __init__(self):
        gtk.GtkFrame.__init__(self, "IRC Account")
        self.add(gtk.GtkButton("IRC!"))
class DummyTRPanel(gtk.GtkFrame):
    def __init__(self):
        gtk.GtkFrame.__init__(self, "Twisted Reality Account")
        self.add(gtk.GtkButton("Reality!"))

registeredTypes = [("Dummy AOL", DummyAOLPanel),
                   ("Dummy IRC", DummyIRCPanel),
                   ("Dummy Twisted Reality", DummyTRPanel)]

class AddContact(gtkutil.GetString):
    def __init__(self, im):
        gtkutil.GetString.__init__(self, im, "Add Contact")

    def clicked(self, btn):
        self.im.remote.addContact(self.entry.get_text())
        self.destroy()



class Conversation(gtk.GtkWindow):
    def __init__(self, im, contact):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.im = im
        self.contact = contact
        self.set_title("%s - Instance Messenger" % contact)
        self.text = gtk.GtkText()
        vb = gtk.GtkVBox()
        gtkutil.defocusify(self.text)
        self.text.set_word_wrap(gtk.TRUE)
        vb.pack_start(gtkutil.scrollify(self.text), 1, 1, 0)
        self.entry = gtk.GtkEntry()
        self.entry.signal_connect('activate', self.sendMessage)
        vb.pack_start(self.entry, 0, 0, 0)
        self.add(vb)
        self.signal_connect('destroy', self.removeFromList, None)
        self.show_all()

    def messageReceived(self, message, sender=None, font=None):
        t = self.text
        t.set_point(t.get_length())
        t.freeze()
        y,mon,d,h,min,sec, ig,no,re = time.localtime(time.time())
        t.insert(font or gtkutil.boldFont, None, None, "%s:%s:%s %s: %s\n"
                 % (h,min,sec,sender or self.contact, message))
        a = t.get_vadjustment()
        t.thaw()
        a.set_value(a.upper - a.page_size)
        self.entry.grab_focus()

    def sendMessage(self, entry):
        txt = self.entry.get_text()
        self.entry.set_text("")
        ms = MessageSent(self.im, self, txt)
        self.im.remote.directMessage(self.contact, txt).addCallbacks(ms.success, ms.failure)

    def removeFromList(self, win, evt):
        del self.im.conversations[self.contact]



class GroupSession(gtk.GtkWindow):
    def __init__(self, groupName, im):
        self.groupName = groupName
        self.im = im

        self.history = ['']
        self.histpos = 0

        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("%s - Instance Messenger" % groupName)
        self.connect('destroy', self.leaveGroup)

        vb = gtk.GtkVBox()
        hb = gtk.GtkHBox()

        self.output = gtk.GtkText()
        self.output.set_word_wrap(gtk.TRUE)
        gtkutil.defocusify(self.output)
        hb.pack_start(gtkutil.scrollify(self.output), 1,1,1)

        userlist = gtk.GtkCList(1, ["Users"])
        userlist.set_shadow_type(gtk.SHADOW_OUT)
        gtkutil.defocusify(userlist)
        hb.pack_start(gtkutil.scrollify(userlist), gtk.TRUE, gtk.TRUE, 0)

#        print self.im.remote.groups
#        for group in self.im.remote.groups:
#            if group.name == groupName:
#                for member in group.members:
#                    userlist.append_items([member.name])

        self.userlist = userlist

        vb.pack_start(hb, 1,1,1)
        self.input = gtk.GtkEntry()
        vb.pack_start(self.input,0,0,1)
        #took this out so I can check in and not be broken
        #self.input.connect('key_press_event', self.processKey)
        self.input.connect('activate', self.sendMessage)
        self.add(vb)
        self.show_all()

    def processKey(self, entry, event):
        if event.keyval == gtk.GDK.Up:
            self.historyUp()
            self.focusInput()
        elif event.keyval == gtk.GDK.Down:
            self.historyDown()
            self.focusInput()

    def focusInput(self):
        self.input.grab_focus()

    def historyUp(self):
        if self.histpos > 0:
            l = self.input.get_text()
            if len(l) > 0 and l[0] == '\n': l = l[1:]
            if len(l) > 0 and l[-1] == '\n': l = l[:-1]
            self.history[self.histpos] = l
            self.histpos = self.histpos - 1
            self.input.set_text(self.history[self.histpos])


    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            l = self.input.get_text()
            if len(l) > 0 and l[0] == '\n': l = l[1:]
            if len(l) > 0 and l[-1] == '\n': l = l[:-1]
            self.history[self.histpos] = l
            self.histpos = self.histpos + 1
            self.input.set_text(self.history[self.histpos])

    def leaveGroup(self, blargh):
        self.im.remote.leaveGroup(self.groupName)
        self.destroy()

    def sendMessage(self, entry):
        val = entry.get_text()
        if not val:
            return
        self.histpos = len(self.history) - 1
        self.history[self.histpos] = val
        self.histpos = self.histpos + 1
        self.history.append('')

        self.im.remote.groupMessage(self.groupName, val)
        self.output.insert_defaults("<<%s>> %s\n" % (self.im.name, val))
        entry.set_text("")

    def displayMessage(self, sender, message):
        self.output.insert_defaults("<%s> %s\n" % (sender,message))

    def memberJoined(self,member):
        self.output.insert_defaults("%s joined!\n" % member)
        #self.userlist.append_items(member)

    def memberLeft(self,member):
        self.output.insert_defaults("%s left!\n" % member)
        #row = self.list.find_row_from_data(intern(contact))
        #if row != -1:
        #    self.list.remove(row)
        #else:
        #    print "uhh.. %s wasn't found." % member

class MessageSent:
    def __init__(self, im, conv, mesg):
        self.im = im
        self.conv = conv
        self.mesg = mesg

    def success(self, result):
        self.conv.messageReceived(self.mesg, self.im.name, gtkutil.normalFont)

    def failure(self, tb):
        self.conv.messageReceived("could not send message %s: %s"
                                  % (repr(self.mesg), tb), "error", gtkutil.errorFont )



class JoinGroup(gtkutil.GetString):
    def __init__(self, im):
        gtkutil.GetString.__init__(self, im, "Join Group")

    def clicked(self, btn):
        val = self.entry.get_text()
        self.im.remote.joinGroup(val)
        self.im.groups[val] = GroupSession(val,self.im)
        self.destroy()


class ContactList(gtk.GtkWindow):
    def __init__(self, im):
        self.im = im
        # Set up the Contact List window.
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        # Cheat, we'll do this correctly later --
        self.signal_connect('destroy', gtk.mainquit, None)
        self.set_title("Instance Messenger")
        # self.set_usize(200,400)

        # Vertical Box packing
        vb = gtk.GtkVBox(gtk.FALSE, 5)

        # Contact List
        self.list = gtk.GtkCList(2, ["Status", "Contact"])
        self.list.set_shadow_type(gtk.SHADOW_OUT)
        self.list.set_column_width(1, 150)
        self.list.set_column_width(0, 50)
        self.list.signal_connect("select_row", self.contactSelected)

        vb.pack_start(gtkutil.scrollify(self.list), gtk.TRUE, gtk.TRUE, 0)

        addContactButton = gtkutil.cbutton("Add Contact", self.addContactWindow)
        removeContactButton = gtkutil.cbutton("Remove Contact", self.removeContact)
        sendMessageButton = gtkutil.cbutton("Send Message", self.sendMessage)
        joinGroupButton = gtkutil.cbutton("Join Group", self.joinGroupWindow)
        hb = gtk.GtkHBox()
        hb.pack_start(addContactButton)
        hb.pack_start(removeContactButton)
        hb.pack_start(sendMessageButton)
        hb.pack_start(joinGroupButton)

        vb.pack_start(hb, gtk.FALSE, gtk.FALSE, 0)
        self.add(vb)
        self.show_all()

    def addContactWindow(self, blargh):
        AddContact(self.im)

    def joinGroupWindow(self, bleh):
        JoinGroup(self.im)

    def removeContact(self, blonk):
        self.im.remote.removeContact(self.list.get_row_data(self.list.selection[0]))
        self.list.remove(self.list.selection[0])

    def contactSelected(self, clist, row, column, event):
        #print 'event on',row
        target = self.list.get_row_data(row)
        if event.type == gtk.GDK._2BUTTON_PRESS:
            #print 'Double Click on', target
            self.im.conversationWith(target)

    def sendMessage(self, blah):
        self.im.conversationWith(self.list.get_row_data(self.list.selection[0]))
        #print 'message send'

    def changeContactStatus(self, contact, newStatus):
        row = self.list.find_row_from_data(intern(contact))
        r = [str(newStatus), contact]
        if row != -1:
            #print 'pre-existing row',row,contact
            self.list.remove(row)
            self.list.insert(row, r)
        else:
            #print 'new row',row,contact
            row = self.list.append(r)
        self.list.set_row_data(row, intern(contact))

im.Conversation=Conversation
im.ContactList=ContactList


def main():
    am = AccountManager(gtk.WINDOW_TOPLEVEL)
    am.show_all()
    gtk.mainloop()
