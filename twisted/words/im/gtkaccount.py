# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


try:
    import cPickle as pickle
except ImportError:
    import pickle

import gtk

from twisted.words.im.gtkcommon import GLADE_FILE, SETTINGS_FILE, autoConnectMethods,\
     openGlade

from twisted.words.im import gtkchat

### This generic stuff uses the word "account" in a very different way -- chat
### accounts are potential sources of messages, InstanceMessenger accounts are
### individual network connections.

class AccountManager:
    def __init__(self):
        self.xml = openGlade(GLADE_FILE, root="MainIMWindow")
        self.chatui = gtkchat.GtkChatClientUI(self.xml)
        self.chatui._accountmanager = self # TODO: clean this up... it's used in gtkchat
        print self.xml._o
        autoConnectMethods(self, self.chatui.theContactsList)
        self.widget = self.xml.get_widget("AccountManWidget")
        self.widget.show_all()
        try:
            f = open(SETTINGS_FILE)
            self.accounts = pickle.load(f)
            print 'loaded!'
            self.refreshAccounts()
        except IOError:
            self.accounts = []
            print 'initialized!'

    def on_ConsoleButton_clicked(self, b):
        #### For debugging purposes...
        from twisted.manhole.ui.pywidgets import LocalInteraction
        l = LocalInteraction()
        l.localNS['chat'] = self.chatui
        l.show_all()

    def created(self, acct):
        self.accounts.append(acct)
        self.refreshAccounts()

    def refreshAccounts(self):
        w = self.xml.get_widget("accountsList")
        w.clear()
        for acct in self.accounts:
            l = [acct.accountName, acct.isOnline() and 'yes' or 'no',
                 acct.autoLogin and 'yes' or 'no', acct.gatewayType]
            w.append(l)

    def lockNewAccount(self, b):
        self.xml.get_widget("NewAccountButton").set_sensitive(not b)

    def on_NewAccountButton_clicked(self, b):
        NewAccount(self)

    def on_MainIMWindow_destroy(self, w):
        print 'Saving...'
        pickle.dump(self.accounts, open(SETTINGS_FILE,'wb'))
        print 'Saved.'
        gtk.mainquit()


    def on_DeleteAccountButton_clicked(self, b):
        lw = self.xml.get_widget("accountsList")
        if lw.selection:
            del self.accounts[lw.selection[0]]
            self.refreshAccounts()

    def on_LogOnButton_clicked(self, b):
        lw = self.xml.get_widget("accountsList")
        if lw.selection:
            self.accounts[lw.selection[0]].logOn(self.chatui)


class DummyAccountForm:
    def __init__(self, manager):
        self.widget = gtk.GtkButton("HELLO")

    def create(self, sname, autoLogin):
        return None


class NewAccount:
    def __init__(self, manager):
        self.manager = manager
        self.manager.lockNewAccount(1)
        self.xml = openGlade(GLADE_FILE, root="NewAccountWindow")
        autoConnectMethods(self)
        self.widget = self.xml.get_widget("NewAccountWindow")
        self.frame = self.xml.get_widget("GatewayFrame")
        # Making up for a deficiency in glade.
        widgetMenu = self.xml.get_widget("GatewayOptionMenu")
        m = gtk.GtkMenu()
        activ = 0
        self.currentGateway = None
        for name, klas in registeredTypes:
            i = gtk.GtkMenuItem(name)
            m.append(i)
            k = klas(self.manager)
            i.connect("activate", self.gatewaySelected, k)
            if not activ:
                activ = 1
                self.gatewaySelected(None, k)
        widgetMenu.set_menu(m)
        self.widget.show_all()

    def gatewaySelected(self, ig, k):
        if self.currentGateway:
            self.frame.remove(self.currentGateway.widget)
        self.currentGateway = k
        self.frame.add(k.widget)
        k.widget.show_all()

    def createAccount(self, b):
        autoLogin = self.xml.get_widget("AutoLogin").get_active()
        accountName = self.xml.get_widget("accountName").get_text()
        x = self.currentGateway.create(accountName, autoLogin)
        if x:
            self.manager.created(x)
            self.destroyMe()

    def destroyMe(self, b=None):
        self.widget.destroy()

    def on_NewAccountWindow_destroy(self, w):
        self.manager.lockNewAccount(0)

from twisted.words.im.pbsupport import PBAccount
from twisted.words.im.tocsupport import TOCAccount
from twisted.words.im.ircsupport import IRCAccount


class PBAccountForm:
    def __init__(self, manager):
        self.manager = manager
        self.xml = openGlade(GLADE_FILE, root="PBAccountWidget")
        autoConnectMethods(self)
        self.widget = self.xml.get_widget("PBAccountWidget")
        self.on_serviceType_changed()
        self.selectedRow = None

    def addPerspective(self, b):
        stype = self.xml.get_widget("serviceType").get_text()
        sname = self.xml.get_widget("serviceName").get_text()
        pname = self.xml.get_widget("perspectiveName").get_text()
        self.xml.get_widget("serviceList").append([stype, sname, pname])

    def removePerspective(self, b):
        if self.selectedRow is not None:
            self.xml.get_widget("serviceList").remove(self.selectedRow)

    def on_serviceType_changed(self, w=None):
        self.xml.get_widget("serviceName").set_text(self.xml.get_widget("serviceType").get_text())
        self.xml.get_widget("perspectiveName").set_text(self.xml.get_widget("identity").get_text())

    on_identity_changed = on_serviceType_changed

    def on_serviceList_select_row(self, slist, row, column, event):
        self.selectedRow = row

    def create(self, accName, autoLogin):
        host = self.xml.get_widget("hostname").get_text()
        port = self.xml.get_widget("portno").get_text()
        user = self.xml.get_widget("identity").get_text()
        pasw = self.xml.get_widget("password").get_text()
        serviceList = self.xml.get_widget("serviceList")
        services = []
        for r in xrange(0, serviceList.rows):
            row = []
            for c in xrange(0, serviceList.columns):
                row.append(serviceList.get_text(r, c))
            services.append(row)
        if not services:
            services.append([
                self.xml.get_widget("serviceType").get_text(),
                self.xml.get_widget("serviceName").get_text(),
                self.xml.get_widget("perspectiveName").get_text()])
        return PBAccount(accName, autoLogin, user, pasw, host, int(port),
                         services)


class TOCAccountForm:
    def __init__(self, maanger):
        self.xml = openGlade(GLADE_FILE, root="TOCAccountWidget")
        self.widget = self.xml.get_widget("TOCAccountWidget")

    def create(self, accountName, autoLogin):
        return TOCAccount(
            accountName, autoLogin,
            self.xml.get_widget("TOCName").get_text(),
            self.xml.get_widget("TOCPass").get_text(),
            self.xml.get_widget("TOCHost").get_text(),
            int(self.xml.get_widget("TOCPort").get_text()) )


class IRCAccountForm:
    def __init__(self, maanger):
        self.xml = openGlade(GLADE_FILE, root="IRCAccountWidget")
        self.widget = self.xml.get_widget("IRCAccountWidget")

    def create(self, accountName, autoLogin):
        return IRCAccount(
            accountName, autoLogin,
            self.xml.get_widget("ircNick").get_text(),
            self.xml.get_widget("ircPassword").get_text(),
            self.xml.get_widget("ircServer").get_text(),
            int(self.xml.get_widget("ircPort").get_text()),
            self.xml.get_widget("ircChannels").get_text(),
            )



registeredTypes = [ ("Twisted", PBAccountForm),
                    ("AOL Instant Messenger", TOCAccountForm),
                    ["IRC", IRCAccountForm],
                    ("Dummy", DummyAccountForm) ]
