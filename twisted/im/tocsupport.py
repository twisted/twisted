from libglade import GladeXML

from twisted.protocols import toc
from twisted.im.locals import GLADE_FILE




class TOCProto(toc.TOCClient):
    def __init__(self, account):
        self.account = account
        toc.TOCClient.__init__(self, account.username, account.password)

    def _debug(self, m):
        print '<toc debug>', repr(m)

    def onLine(self):
        self.account.online = 1
        print '$$!&*$&!(@$*& TOC ONLINE *!#@&$(!*%&'

    def gotConfig(self, mode, buddylist, permit, deny):
        print 'got toc config', repr(mode), repr(buddylist), repr(permit), repr(deny)
        if permit:
            self._debug('adding permit')
            self.add_permit(permit)
        if deny:
            self._debug('adding deny')
            self.add_deny(deny)
        for k in buddylist.keys():
            for u in buddylist[k]:
                self.add_buddy([u])
        self.signon()

    ### Error Messages
    def hearError(self, code, args):
        print '*** TOC ERROR ***', repr(code), repr(args)
    def hearWarning(self, newamount, username):
        print '*** TOC ERROR ***', repr(newamount), repr(username)

    ### Buddy Messages
    def hearMessage(self,username,message,autoreply):
        print '*** TOC MESSAGE ***', username, message, autoreply
    def updateBuddy(self,username,online,evilness,signontime,idletime,userclass,away):
        print '*** TOC BUDDY ***', username

    ### Group Chat
    def chatJoined(self, roomid, roomname, users):
        print '*** TOC ROOM JOINED ***', roomid, roomname, users
    def chatUpdate(self,roomid,username,inroom):
        print '*** USER JOINED/LEFT ROOM ***', roomid, username, inroom
    def chatHearMessage(self, roomid, username, message):
        print '*** USER TO ROOM ***', roomid, username, message
    def chatHearWhisper(self, roomid, username, message):
        print '*** user whispered *** ', roomimd, username, message
    def chatInvited(self, roomid, roomname, username, message):
        print '*** user whispered *** ',roomimd, roomname, username, message
    def chatLeft(self, roomid):
        print '*** We left. ***', roomid
    def rvousProposal(self,type,cookie,user,vip,port,**kw):
        print '*** rendezvous. ***', type, cookie, user, vip, port, kw
    def receiveBytes(self, user, file, chunk, sofar, total):
        print '*** File transfer! ***', user, file, chunk, sofar, total

class TOCAccount:
    gatewayType = "AIM (TOC)"
    def __init__(self, accountName, autoLogin, username, password, host, port):
        self.accountName = accountName
        self.autoLogin = autoLogin
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.online = 0

    def __setstate__(self, d):
        self.__dict__ = d
        self.port = int(self.port)

    def __getstate__(self):
        self.online = 0
        return self.__dict__

    def isOnline(self):
        return self.online

    def logOn(self):
        tcp.Client(self.host, self.port, TOCProto(self))

class TOCAccountForm:
    def __init__(self, maanger):
        self.xml = GladeXML(GLADE_FILE, root="TOCAccountWidget")
        self.widget = self.xml.get_widget("TOCAccountWidget")

    def create(self, accountName, autoLogin):
        return TOCAccount(
            accountName, autoLogin,
            self.xml.get_widget("TOCName").get_text(),
            self.xml.get_widget("TOCPass").get_text(),
            self.xml.get_widget("TOCHost").get_text(),
            int(self.xml.get_widget("TOCPort").get_text()) )
