class AccountManager:
    def __init__(self):
        self.accounts = {}

    def getSnapShot(self):
        """getSnapShot() : list{list{string:accountName, boolean:isOnline,
                                     boolean:autoLogin, string:gatewayType}}
        Returns a snapshot of all the accounts so that a GUI can display it"""
        data = []
        for account in self.accounts.values():
            data.append([account.accountName, account.isOnline(),
                         account.autoLogin, account.gatewayType])
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
        self.accounts[accountName].logOn(chatui)

    def disconnect(self, accountName):
        pass 
        #self.accounts[accountName].logOff()  - not yet implemented

    def quit(self):
        pass
        #for account in self.accounts.values():
        #    account.logOff()  - not yet implemented
