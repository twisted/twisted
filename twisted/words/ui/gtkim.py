
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

def defocusify(widget):
    widget.unset_flags(gtk.CAN_FOCUS)



class AddContact(gtk.GtkWindow):
    def __init__(self, contactList):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Add Contact")
        self.contactList = contactList
        button = gtkutil.cbutton("Add Contact", self.clicked)
        self.entry = gtk.GtkEntry()
        hb = gtk.GtkHBox()
        hb.add(self.entry)
        hb.add(button)
        self.add(hb)
        self.show_all()

    def clicked(self, btn):
        self.contactList.persp.addContact(self.entry.get_text())
        self.destroy()


normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
errorFont = gtk.load_font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")

class Conversation(gtk.GtkWindow):
    def __init__(self, contactList, contact):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.contactList = contactList
        self.contact = contact
        self.set_title("%s - Instance Messenger" % contact)
        self.text = gtk.GtkText()
        vb = gtk.GtkVBox()
        defocusify(self.text)
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
        t.insert(font or boldFont, None, None, "%s:%s:%s %s: %s\n"
                 % (h,min,sec,sender or self.contact, message))
        a = t.get_vadjustment()
        t.thaw()
        a.set_value(a.upper - a.page_size)
        self.entry.grab_focus()

    def sendMessage(self, entry):
        txt = self.entry.get_text()
        self.entry.set_text("")
        ms = MessageSent(self, txt)
        self.contactList.persp.directMessage(self.contact, txt,
                                             pbcallback=ms.success,
                                             pberrback=ms.failure)

    def removeFromList(self, win, evt):
        del self.contactList.conversations[self.contact]

class MessageSent:
    def __init__(self, conv, mesg):
        self.conv = conv
        self.mesg = mesg

    def success(self, result):
        self.conv.messageReceived(self.mesg, self.conv.contactList.name, normalFont)

    def failure(self, tb):
        self.conv.messageReceived("could not send message %s: %s"
                                  % (repr(self.mesg), tb), "error", errorFont )
        

class ContactList(gtk.GtkWindow, pb.Referenced):
    def __init__(self):
        # Set up the Contact List window.
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        # Cheat, we'll do this correctly later --
        self.signal_connect('destroy', gtk.mainquit, None)
        self.set_title("Instance Messenger")
        # self.set_usize(200,400)
        
        self.conversations = {}
        
        # Vertical Box packing
        vb = gtk.GtkVBox(gtk.FALSE, 5)
        
        # Contact List
        self.list = gtk.GtkCList(2, ["Status", "Contact"])
        self.list.set_shadow_type(gtk.SHADOW_OUT)
        self.list.set_column_width(1, 150)
        self.list.set_column_width(0, 50)
        self.list.signal_connect("select_row", self.contactSelected)
        
        vb.pack_start(gtkutil.scrollify(self.list), gtk.TRUE, gtk.TRUE, 0)
        
        addContactButton = gtkutil.cbutton("Add Contact", self.addContact)
        sendMessageButton = gtkutil.cbutton("Send Message", self.sendMessage)
        hb = gtk.GtkHBox()
        hb.pack_start(addContactButton)
        hb.pack_start(sendMessageButton)
        
        vb.pack_start(hb, gtk.FALSE, gtk.FALSE, 0)
        self.add(vb)

    def addContact(self, button):
        AddContact(self)

    def conversationWith(self, target):
        x = self.conversations.get(target)
        if not x:
            x = Conversation(self, target)
            self.conversations[target] = x
        return x

    def remote_receiveDirectMessage(self, sender, message):
        w = self.conversationWith(sender)
        w.messageReceived(message)
    
    def contactSelected(self, clist, row, column, event):
        print 'event on',row
        target = self.list.get_row_data(row)
        if event.type == gtk.GDK._2BUTTON_PRESS:
            print 'Double Click on', target
            self.conversationWith(target)

    def sendMessage(self, blah):
        print 'message send'

    def connected(self, perspective):
        self.name = lw.username.get_text()
        lw.hide()
        self.persp = perspective
        self.show_all()

    def remote_receiveContactList(self, contacts):
        print 'got contacts'
        for contact, status in contacts:
            row = self.list.append([str(status), contact])
            print 'list',row,contact
            self.list.set_row_data(row, intern(contact))

    def remote_notifyStatusChanged(self, contact, newStatus):
        print "status change",contact, newStatus
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

def main():
    global lw
    b = ContactList()
    lw = gtkutil.Login(b.connected, b,
                       initialPassword="guest",
                       initialService="twisted.words")
    lw.show_all()
    gtk.mainloop()


