
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

from twisted.protocols import toc
from twisted.internet import tcp
from twisted.words.ui import gateway
import string,re

shortName="TOC"
longName="AOL Instant Messenger/TOC"

loginOptions=[
    ["text","Nickname","username","my_screen_name"],
    ["password","Password","password","my_password"],
    ["text","Hostname","server","toc.oscar.aol.com"],
    ["text","Port #","port","9898"]]

def makeConnection(im,server=None,port=None,**kwargs):
    try:
        port=int(port)
    except:
        pass
    c=apply(TOCGateway,(),kwargs)
    c.attachIM(im)
    tcp.Client(server,port,c)
    
def dehtml(text):
    text=re.sub('<.*?>','',text)
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&nbsp;',' ')
    text=string.replace(text,'&#34;','"')
    return text

class TOCGateway(gateway.Gateway,toc.TOCClient):
    """This is the interface between IM and a TOC server
    """
    protocol=shortName
    
    def __init__(self,username,password,*args,**kw):
        gateway.Gateway.__init__(self)
        apply(toc.TOCClient.__init__,(self,username,password)+args,kw)
        self.name="%s (%s)"%(username,self.protocol)
        self.logonUsername=username
        self._chatmapping={}
        self._roomid={}

    def _debug(self,text):
        pass

    def connectionFailed(self):
        self.im.send(self,"error",message="Connection Failed!")
        self.detachIM()

    def connectionLost(self):
        if self.im:
            self.im.send(self,"error",message="Connection lost.")
            self.detachIM()

    def hearError(self,code,args):
        if code in [toc.BAD_ACCOUNT,toc.BAD_NICKNAME,toc.SERVICE_UNAVAILABLE,
                    toc.BAD_NICKNAME,toc.SERVICE_TEMP_UNAVAILABLE,
                    toc.WARNING_TOO_HIGH,toc.CONNECTING_TOO_QUICK,
                    toc.UNKNOWN_SIGNON]:
            self.im.send(self,"error",message=toc.STD_MESSAGE[code]%args+".")
            self.detachIM()

    def loseConnection(self):
        self.transport.loseConnection()
        
#    def tocNICK(self,data):
#        self.changeContactName(self.username,data[0])
#        #self.username=data[0]
    
    def gotConfig(self,mode,buddylist,permit,deny):
        users=[]
        self._currentusers=[]
        for k in buddylist.keys():
            for u in buddylist[k]:
                self.add_buddy([u])
                users.append((u,"Offline"))
                self._currentusers.append(u)
        if permit:
            self.add_permit(permit)
        if deny:
            self.add_deny(deny)
        self.signon()
        self.receiveContactList(users)
        self._savedmode=mode
        self._savedlist=buddylist or {}
        #self._savedpermit=permit
        #self._saveddeny=deny
        
    def updateName(self,user):
        for u in self._currentusers:
            if toc.normalize(u)==toc.normalize(user): # same user
                if user!=u: # whoopsies, name change
                    self.notifyNameChanged(u,user)
                    i=self._currentusers.index(u)
                    self._currentusers[i]=user

    def hearMessage(self,user,message,autoreply):
        message=dehtml(message)
        if autoreply: message="<AUTO-REPLY>: "+message
        self.updateName(user)
        self.receiveDirectMessage(user,message)
        if self.isaway() and not autoreply:
            self.say(user,self._awaymessage,1)

    def updateBuddy(self,user,online,evilness,signontime,idletime,userclass,away):
        state="Online"
        if idletime>0: state="Idle"
        if away: state="Away"
        if not online: state="Offline"
        self.updateName(user)
        self.notifyStatusChanged(user,state)
        
    def chatJoined(self,roomid,roomname,users):
        if self._chatmapping.has_key(toc.normalize(roomname)):roomname=self._chatmapping[toc.normalize(roomname)]
        self._roomid[roomid]=roomname
        self.joinedGroup(roomname)
        self.receiveGroupMembers(users, roomname)

    def chatUpdate(self,roomid,user,inroom):
        self.updateName(user)
        if inroom:
            self.memberJoined(user, self._roomid[roomid])
        else:
            self.memberLeft(user, self._roomid[roomid])

    def chatHearMessage(self,roomid,user,message):
        if user==self.username: return
        message=dehtml(message)
        self.updateName(user)
        self.receiveGroupMessage(user,self._roomid[roomid],message)

    def chatLeft(self,roomid):
        roomname=self._roomid[roomid]
        if self._chatmapping.has_key(toc.normalize(roomname)):
            del self._chatmapping[toc.normalize(roomname)]
        del self._roomid[roomid]
        self.leftGroup(roomname)
    
    def writeNewConfig(self):
        self.set_config(self._savedmode,self._savedlist,self._permitlist,self._denylist)

    def event_addContact(self,contact):
        self.add_buddy([contact])
        try:
            k=self._savedlist.keys()[0]
        except IndexError:
            k="Twisted Buddies"
            self._savedlist[k]=[]
        self._savedlist[k].append(contact)
        self._currentusers.append(contact)
        self.writeNewConfig()
        self.notifyStatusChanged(contact,"Offline")

    def event_removeContact(self,contact):
        self.del_buddy([contact])
        n=toc.normalize(contact)
        for u in range(len(self._currentusers)):
            if toc.normalize(self._currentusers[u])==n:
                del self._currentusers[u]
                break
        for k in self._savedlist.keys():
            for u in range(len(self._savedlist[k])):
                if n==toc.normalize(self._savedlist[k][u]):
                    del self._savedlist[k][u]
                    self.writeNewConfig()
                    return

    def event_changeStatus(self,status):
        if status=="Online":
            self.away('')
        elif status=="Away":
            self.away("I'm not here right now.  Leave a message.")

    def event_joinGroup(self,group):
        n=toc.normalize(group)
        if self._chatmapping.has_key(n):
            return 1
        self._chatmapping[n]=group
        self.chat_join(4,group)

    def event_leaveGroup(self,group):
        for i in self._roomid.keys():
            if self._roomid[i]==group:
                self.chat_leave(i)

    def event_getGroupMembers(self,group):
        pass
        
    def event_directMessage(self,user,message):
        self.say(user,message)

    def event_groupMessage(self,group,message):
        for k in self._roomid.keys():
            if self._roomid[k]==group:
                id=k
        if not id: return
        self.chat_say(id,message)

def warnUser(im,gateway,user,text):
    gateway.evil(user)
    return text

def warnUserAnonymously(im,gateway,user,text):
    gateway.evil(user,1)
    return text

def blockUser(im,gateway,user,text):
    gateway.add_deny([user])
    gateway.writeNewConfig()
    return text

def unBlockUser(im,gateway,user,text):
    gateway.del_deny([user])
    gateway.writeNewConfig()
    return text

def chatInvite(im,gateway,group,text,users):
    users=string.split(text,",")
    for k in gateway._roomid.keys():
        if gateway._roomid[k]==group:
            id=k
    gateway.chat_invite(id,users,"Join me in this buddy chat.")
    return ""

def sendIM(im,gateway,group,text,users):
    for u in users:
        im.conversationWith(gateway,u)
    return text

groupExtras=[
    ["Send Chat Invitation",chatInvite],
    ["Send IM",sendIM]
]

conversationExtras=[
    ["Warn",warnUser],
    ["Warn Anonymously",warnUserAnonymously],
    ["Block",blockUser],
    ["Unblock",unBlockUser]
]

contactListExtras=[]
