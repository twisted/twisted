# -*- Python -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2002-2003 Matthew W. Lefkowitz
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
#


class AccountManager:
    """I am responsible for managing a user's accounts.

    That is, remembering what accounts are available, their settings,
    adding and removal of accounts, etc.

    @ivar accounts: A collection of available accounts.
    @type accounts: mapping of strings to L{Account<interfaces.IAccount>}s.
    """
    def __init__(self):
        self.accounts = {}

    def getSnapShot(self):
        """A snapshot of all the accounts and their status.

        @returns: A list of tuples, each of the form
            (string:accountName, boolean:isOnline,
            boolean:autoLogin, string:gatewayType)
        """
        data = []
        for account in self.accounts.values():
            data.append((account.accountName, account.isOnline(),
                         account.autoLogin, account.gatewayType))
        return data

    def isEmpty(self):
        return len(self.accounts) == 0

    def getConnectionInfo(self):
        connectioninfo = []
        for account in self.accounts.values():
            connectioninfo.append(account.isOnline())
        return connectioninfo

    def addAccount(self, account):
        self.accounts[account.accountName] = account

    def delAccount(self, accountName):
        del self.accounts[accountName]

    def connect(self, accountName, chatui):
        """
        @returntype: Deferred L{interfaces.IClient}
        """
        return self.accounts[accountName].logOn(chatui)

    def disconnect(self, accountName):
        pass
        #self.accounts[accountName].logOff()  - not yet implemented

    def quit(self):
        pass
        #for account in self.accounts.values():
        #    account.logOff()  - not yet implemented
