import string, re

from twisted.protocols import toc
from twisted.im.locals import GLADE_FILE, autoConnectMethods, ONLINE, OFFLINE, AWAY, openGlade
from twisted.im.chat import getContactsList, getGroup, getGroupConversation, getPerson, getConversation
from twisted.internet import tcp
from twisted.python.defer import succeed
      
def dehtml(text):
    text=string.replace(text,"<br>","\n")
    text=string.replace(text,"<BR>","\n")
    text=string.replace(text,"<Br>","\n") # XXX make this a regexp
    text=string.replace(text,"<bR>","\n")
    text=re.sub('<.*?>','',text)
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&nbsp;',' ')
    text=string.replace(text,'&#34;','"')
    return text

def html(text):
    text=string.replace(text,'"','&#34;')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,"\n","<br>")
    return '<html><body bgcolor="white"><font color="black">%s</font></body></html>'%text

class TOCPerson:
    def __init__(self,name,tocClient):
        self.name=name
        self.account=tocClient
        self.status=OFFLINE

    def isOnline(self):
        return self.status!=OFFLINE

    def getStatus(self):
        return {OFFLINE:'Offline',ONLINE:'Online',AWAY:'Away'}[self.status]

    def setStatus(self,status):
        self.status=status
        getContactsList().setContactStatus(self)

    def sendMessage(self, text, meta=None):
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.account.say(self.name,html(text))
        return succeed(text)

class TOCGroup:
    def __init__(self,name,tocClient):
        self.name=name
        self.account=tocClient
        self.roomID=self.account.roomID[name]

    def sendGroupMessage(self, text, meta=None):
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.account.chat_say(self.roomID,html(text))
        return succeed(text)

    def leave(self):
        self.account.chat_leave(self.roomID)
        
class TOCProto(toc.TOCClient):
    def __init__(self, account):
        self.account = account
        toc.TOCClient.__init__(self, account.username, account.password)
        self.roomID={}
        self.roomIDreverse={}

    def _debug(self, m):
        pass #print '<toc debug>', repr(m)

    def getGroupConversation(self, name,hide=0):
        return getGroupConversation(getGroup(name,self,TOCGroup),hide)

    def getPerson(self,name):
        return getPerson(name,self,TOCPerson)

    def onLine(self):
        self.account.isOnline = 1
        #print '$$!&*$&!(@$*& TOC ONLINE *!#@&$(!*%&'

    def gotConfig(self, mode, buddylist, permit, deny):
        #print 'got toc config', repr(mode), repr(buddylist), repr(permit), repr(deny)
        if permit:
            self._debug('adding permit')
            self.add_permit(permit)
        if deny:
            self._debug('adding deny')
            self.add_deny(deny)
        clist=[]
        for k in buddylist.keys():
            self.add_buddy(buddylist[k])
            for name in buddylist[k]:
                self.getPerson(name).setStatus(OFFLINE)
        self.signon()
        
    def tocNICK(self,data):
        self.name=data[0]
        self.accountName = "%s (TOC)"%data[0]
        registerAccount(self)
        getContactsList()

    ### Error Messages
    def hearError(self, code, args):
        print '*** TOC ERROR ***', repr(code), repr(args)
    def hearWarning(self, newamount, username):
        print '*** TOC ERROR ***', repr(newamount), repr(username)
    ### Buddy Messages
    def hearMessage(self,username,message,autoreply):
        if autoreply:
            message='<AUTO-REPLY>: '+message
        getConversation(self.getPerson(username)).showMessage(dehtml(message))
    def updateBuddy(self,username,online,evilness,signontime,idletime,userclass,away):
        if online: status=ONLINE
        elif away: status=AWAY
        else: status=OFFLINE
        self.getPerson(username).setStatus(status)

    ### Group Chat
    def chatJoined(self, roomid, roomname, users):
        self.roomID[roomname]=roomid
        self.roomIDreverse[roomid]=roomname
        self.getGroupConversation(roomname).setGroupMembers(users)
    def chatUpdate(self,roomid,member,inroom):
        group=self.roomIDreverse[roomid]
        if inroom:
            self.getGroupConversation(group).memberJoined(member)
        else:
            self.getGroupConversation(group).memberLeft(member)
    def chatHearMessage(self, roomid, username, message):
        group=self.roomIDreverse[roomid]
        self.getGroupConversation(group).showGroupMessage(username, dehtml(message))
    def chatHearWhisper(self, roomid, username, message):
        print '*** user whispered *** ', roomimd, username, message
    def chatInvited(self, roomid, roomname, username, message):
        print '*** user invited us to chat *** ',roomid, roomname, username, message
    def chatLeft(self, roomid):
        group=self.roomIDreverse[roomid]
        self.getGroupConversation(group,1)
        del self.roomID[group]
        del self.roomIDreverse[roomid]
    def rvousProposal(self,type,cookie,user,vip,port,**kw):
        print '*** rendezvous. ***', type, cookie, user, vip, port, kw
    def receiveBytes(self, user, file, chunk, sofar, total):
        print '*** File transfer! ***', user, file, chunk, sofar, total

    # GTKIM calls
    def joinGroup(self,name):
        self.chat_join(4,toc.normalize(name))

class TOCAccount:
    gatewayType = "AIM (TOC)"
    def __init__(self, accountName, autoLogin, username, password, host, port):
        self.accountName = accountName
        self.autoLogin = autoLogin
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.isOnline = 0

    def __setstate__(self, d):
        self.__dict__ = d
        self.port = int(self.port)

    def __getstate__(self):
        self.isOnline = 0
        return self.__dict__

    def isOnline(self):
        return self.isOnline

    def logOn(self):
        tcp.Client(self.host, self.port, TOCProto(self))

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

from twisted.im.account import registerAccount
