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

import cPickle

import gtk

from twisted.im.locals import GLADE_FILE, SETTINGS_FILE, autoConnectMethods,\
     openGlade


### This generic
### stuff uses the word "account" in a very different way -- chat accounts are
### potential sources of messages, InstanceMessenger accounts are individual
### network connections.

class AccountManager:
    def __init__(self):
        self.xml = openGlade(GLADE_FILE, root="AccountManager")
        print self.xml._o
        autoConnectMethods(self)
        self.widget = self.xml.get_widget("AccountManager")
        self.widget.show_all()
        try:
            f = open(SETTINGS_FILE)
            self.accounts = cPickle.load(f)
            print 'loaded!'
            self.refreshAccounts()
        except IOError:
            self.accounts = []
            print 'initialized!'

    def created(self, acct):
        self.accounts.append(acct)
        self.refreshAccounts()

    def refreshAccounts(self):
        w = self.xml.get_widget("accountsList")
        w.clear()
        for acct in self.accounts:
            l = [acct.accountName, acct.isOnline and 'yes' or 'no', acct.autoLogin and 'yes' or 'no', acct.gatewayType]
            w.append(l)

    def lockNewAccount(self, b):
        self.xml.get_widget("NewAccountButton").set_sensitive(not b)

    def on_NewAccountButton_clicked(self, b):
        NewAccount(self)

    def on_AccountManager_destroy(self, w):
        print 'Saving...'
        cPickle.dump(self.accounts, open(SETTINGS_FILE,'wb'))
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
            self.accounts[lw.selection[0]].logOn()
            



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

onlineAccounts = []                     # list of message sources currently online

def registerAccount(account):
    onlineAccounts.append(account)

def unregisterAccount(account):
    onlineAccounts.remove(account)


from twisted.im.pbsupport import PBAccountForm
from twisted.im.tocsupport import TOCAccountForm
from twisted.im.ircsupport import IRCAccountForm

registeredTypes = [ ("Twisted", PBAccountForm),
                    ("AOL Instant Messenger", TOCAccountForm),
                    ["IRC", IRCAccountForm],
                    ("Dummy", DummyAccountForm) ]
