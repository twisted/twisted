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
import string, re

# Twisted Imports
from twisted.protocols import toc
from twisted.im.locals import ONLINE, OFFLINE, AWAY
from twisted.internet import reactor
from twisted.python.defer import succeed

# Sibling Imports
import basesupport

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
    return '<font color="#000000" back="#ffffff" size=3>%s</font>'%text

class TOCPerson(basesupport.AbstractPerson):
    def isOnline(self):
        return self.status != OFFLINE

    def getStatus(self):
        return {OFFLINE:'Offline',ONLINE:'Online',AWAY:'Away'}[self.status]

    def getIdleTime(self):
        return str(self.idletime)

    def setStatusAndIdle(self, status, idletime):
        self.status = status
        self.idletime = idletime
        self.chat.getContactsList().setContactStatus(self)

    def sendMessage(self, text, meta=None):
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.client.say(self.name,html(text))
        return succeed(text)

class TOCGroup(basesupport.AbstractGroup):
    def __init__(self,name,tocClient,chatui):
        basesupport.AbstractGroup.__init__(self, name, tocClient, chatui)
        self.roomID = self.client.roomID[self.name]

    def sendGroupMessage(self, text, meta=None):
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.client.chat_say(self.roomID,html(text))
        return succeed(text)

    def leave(self):
        self.client.chat_leave(self.roomID)

class TOCProto(basesupport.AbstractClientMixin, toc.TOCClient):
    def __init__(self, account, chatui):
        toc.TOCClient.__init__(self, account.username, account.password)
        basesupport.AbstractClientMixin.__init__(self, account, chatui)
        self.accountName = self.account.username
        self.roomID = {}
        self.roomIDreverse = {}

    def _debug(self, m):
        pass #print '<toc debug>', repr(m)

    def getGroupConversation(self, name,hide=0):
        return self.chat.getGroupConversation(
            self.chat.getGroup(name,self,TOCGroup),
            hide)

    def addContact(self, name):
        self.add_buddy([name])

    def getPerson(self,name):
        return self.chat.getPerson(name,self,TOCPerson)

    def onLine(self):
        self.account._isOnline = 1
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
                self.getPerson(name).setStatusAndIdle(OFFLINE, '--')
        self.signon()
    name = None
    def tocNICK(self,data):
        if not self.name:
            print 'Waiting for second NICK', data
            self.name=data[0]
            self.chat.getContactsList()
        else:
            print 'reregistering...?', data
            self.name=data[0]
            # self.accountName = "%s (TOC)"%data[0]
            self.chat.registerAccountClient(self)

    ### Error Messages
    def hearError(self, code, args):
        print '*** TOC ERROR ***', repr(code), repr(args)
    def hearWarning(self, newamount, username):
        print '*** TOC WARNING ***', repr(newamount), repr(username)
    ### Buddy Messages
    def hearMessage(self,username,message,autoreply):
        if autoreply:
            message='<AUTO-REPLY>: '+message
        self.chat.getConversation(self.getPerson(username)
                             ).showMessage(dehtml(message))
    def updateBuddy(self,username,online,evilness,signontime,idletime,userclass,away):
        if online:
            status=ONLINE
        elif away:
            status=AWAY
        else:
            status=OFFLINE
        self.getPerson(username).setStatusAndIdle(status, idletime)

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

    def joinGroup(self,name):
        self.chat_join(4,toc.normalize(name))

class TOCAccount(basesupport.AbstractAccount):
    gatewayType = "AIM (TOC)"
    
    def __init__(self, accountName, autoLogin, username, password, host, port):
        self.accountName = accountName
        self.autoLogin = autoLogin
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    def startLogOn(self, chatui):
        reactor.clientTCP(self.host, self.port, TOCProto(self, chatui))

