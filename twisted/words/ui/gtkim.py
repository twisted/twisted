
# System Imports
import gtk
from twisted.internet import ingtkernet
ingtkernet.install()

# Twisted Imports
from twisted.spread import pb
from twisted.spread.ui import gtkutil

class Participant(pb.Cache):
    """A local cache of a participant...
    """

class Group(pb.Cache):
    """A local cache of a group.
    """

pb.setCopierForClass("twisted.words.service.Participant", Participant)
pb.setCopierForClass("twisted.words.service.Group", Group)

def scrollify(widget):
    scrl=gtk.GtkScrolledWindow(None, None)
    scrl.add(widget)
    scrl.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
    # scrl.set_update_policy(gtk.POLICY_AUTOMATIC)
    return scrl

def cbutton(name, cb):
    b = gtk.GtkButton(name)
    b.signal_connect ("clicked", cb)
    return b


class AddContact(gtk.GtkWindow):
    def __init__(self, contactList):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Add Contact")
        self.contactList = contactList
        button = cbutton("Add Contact", self.clicked)
        self.entry = gtk.GtkEntry()
        hb = gtk.GtkHBox()
        hb.add(self.entry)
        hb.add(button)
        self.add(hb)
        self.show_all()

    def clicked(self, btn):
        self.contactList.persp.addContact(self.entry.get_text())

class ContactList(gtk.GtkWindow, pb.Referenced):
    def __init__(self):
        # Set up the Contact List window.
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
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

        vb.pack_start(scrollify(self.list), gtk.TRUE, gtk.TRUE, 0)
        
        # Add Contact button.
        adbud = cbutton("Add Contact", self.addContact)
        
        vb.pack_start(adbud, gtk.FALSE, gtk.FALSE, 0)
        self.add(vb)

    def addContact(self, button):
        AddContact(self)

    def connected(self, perspective):
        lw.hide()
        self.persp = perspective
        self.show_all()

    def remote_receiveContactList(self, contacts):
        print 'got contacts'
        for contact in contacts:
            self.list.append([str(contact.status), contact.name])

    def remote_notifyStatusChanged(self, contact, newStatus):
        print contact, newStatus

def main():
    global lw
    b = ContactList()
    lw = gtkutil.Login(b.connected, b, initialPassword="guest")
    lw.show_all()
    gtk.mainloop()


