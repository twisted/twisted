
# System Imports
import gtk
import time
from twisted.internet import ingtkernet
ingtkernet.install()

# Twisted Imports
from twisted.spread import pb
from twisted.spread.ui import gtkutil

class Group(pb.Cache):
    """A local cache of a group.
    """

pb.setCopierForClass("twisted.words.service.Group", Group)


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
        self.im.remote.directMessage(self.contact, txt,
                                             pbcallback=ms.success,
                                             pberrback=ms.failure)

    def removeFromList(self, win, evt):
        del self.im.conversations[self.contact]

class GroupSession(gtk.GtkWindow):
    def __init__(self, groupName, im):
        self.groupName = groupName
        self.im = im
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("%s - Instance Messenger" % self.im.name)
        self.connect('destroy', self.leaveGroup)
        
        self.vb = gtk.GtkVBox()
        self.output = gtk.GtkText()
        self.output.set_word_wrap(gtk.TRUE)
        self.vb.pack_start(gtkutil.scrollify(self.output), 1,1,1)

        self.input = gtk.GtkEntry()
        self.vb.pack_start(self.input,0,0,1)
        self.input.connect('activate', self.sendMessage)
        self.add(self.vb)
        self.show_all()


    def leaveGroup(self, blargh):
        self.im.remote.leaveGroup(self.groupName)
        self.destroy()

    def sendMessage(self, entry):
        val = entry.get_text()
        self.im.remote.groupMessage(self.groupName, val)
        self.output.insert_defaults("<<%s>> %s\n" % (self.im.name, val))
        entry.set_text("")

    def displayMessage(self, sender, message):
        self.output.insert_defaults("<%s> %s\n" % (sender,message))

    def memberJoined(self,member):
        self.output.insert_defaults("%s joined!\n" % member)

    def memberLeft(self,member):
        self.output.insert_defaults("%s left!\n" % member)
        

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
        sendMessageButton = gtkutil.cbutton("Send Message", self.sendMessage)
        joinGroupButton = gtkutil.cbutton("Join Group", self.joinGroupWindow)
        hb = gtk.GtkHBox()
        hb.pack_start(addContactButton)
        hb.pack_start(sendMessageButton)
        hb.pack_start(joinGroupButton)
        
        vb.pack_start(hb, gtk.FALSE, gtk.FALSE, 0)
        self.add(vb)
        self.show_all()

    def addContactWindow(self, blargh):
        AddContact(self.im)

    def joinGroupWindow(self, bleh):
        JoinGroup(self.im)

    def contactSelected(self, clist, row, column, event):
        print 'event on',row
        target = self.list.get_row_data(row)
        if event.type == gtk.GDK._2BUTTON_PRESS:
            print 'Double Click on', target
            self.im.conversationWith(target)

    def sendMessage(self, blah):
        print 'message send'

    def changeContactStatus(self, contact, newStatus):
        row = self.list.find_row_from_data(intern(contact))
        r = [str(newStatus), contact]
        if row != -1:
            print 'pre-existing row',row,contact
            self.list.remove(row)
            self.list.insert(row, r)
        else:
            print 'new row',row,contact
            row = self.list.append(r)
        self.list.set_row_data(row, intern(contact))


class InstanceMessenger(pb.Referenced):
    """This is a broker between the PB broker and the various windows
    that make up InstanceMessenger."""

    def __init__(self):
        self.conversations = {}
        self.groups = {}

    def conversationWith(self, target):
        conv = self.conversations.get(target)
        if not conv:
            conv = Conversation(self, target)
            self.conversations[target] = conv
        return conv

#The PB interface.
    def connected(self, perspective):
        self.name = lw.username.get_text()
        lw.hide()
        self.remote = perspective

    def remote_receiveContactList(self,contacts):
        print 'got contacts'
        self.cl = ContactList(self)
        for contact,status in contacts:
            self.cl.changeContactStatus(contact,status)

    def remote_receiveDirectMessage(self, sender, message):
        #make sure we've started the conversation
        w = self.conversationWith(sender) 
        w.messageReceived(message)

    def remote_notifyStatusChanged(self,contact,newStatus):
        print contact,"changed status to",newStatus
        self.cl.changeContactStatus(contact,newStatus)


    def remote_receiveGroupMessage(self,member,group,message):
        self.groups[group].displayMessage(member,message)

    def remote_memberJoined(self,member,group):
        self.groups[group].memberJoined(member)

    def remote_memberLeft(self,member,group):
        self.groups[group].memberLeft(member)


        
def main():
    global lw
    b = InstanceMessenger()
    lw = gtkutil.Login(b.connected, b,
                       initialPassword="guest",
                       initialService="twisted.words")
    lw.show_all()
    gtk.mainloop()


