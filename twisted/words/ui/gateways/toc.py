
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

loginOptions=[["Nickname","username","my_screen_name"],["Password","password","my_password"],["Hostname","server","toc.oscar.aol.com"],["Port #","port","9898"]]

def makeConnection(im,server=None,port=None,**kwargs):
    try:
        port=int(port)
    except:
        pass
    c=apply(TOCGateway,(),kwargs)
    im.attachGateway(c)
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
        self._usermapping={}
        self._chatmapping={}
        self._roomid={}

    def _debug(self,text):
        pass

    def connectionFailed(self):
        self.im.connectionFailed(self,"Connection Failed!")
        self.im.detachGateway(self)

    def connectionLost(self):
        self.im.connectionLost(self,"Connection lost.")
        self.im.detachGateway(self)

    def gotConfig(self,mode,buddylist,permit,deny):
        users=[]
        for k in buddylist.keys():
            for u in buddylist[k]:
                self.add_buddy([u])
                users.append((u,"Offline"))
        self.add_deny([])
        self.signon()
        self.receiveContactList(users)
        self._savedmode=mode
        self._savedlist=buddylist
        self._savedpermit=permit
        self._saveddeny=deny
        
    def hearMessage(self,user,message,autoreply):
        message=dehtml(message)
        if autoreply: message="<AUTO-REPLY>: "+message
        if self._usermapping.has_key(toc.normalize(user)):user=self._usermapping[toc.normalize(user)]
        self.receiveDirectMessage(user,message)

    def updateBuddy(self,user,online,evilness,signontime,idletime,userclass,away):
        state="Online"
        if idletime>0: state="Idle"
        if away: state="Away"
        if not online: state="Offline"
        if self._usermapping.has_key(toc.normalize(user)):user=self._usermapping[toc.normalize(user)]
        self.notifyStatusChanged(user,state)
        
    def chatJoined(self,roomid,roomname):
        if self._chatmapping.has_key(toc.normalize(roomname)):roomname=self._chatmapping[toc.normalize(roomname)]
        self._roomid[roomid]=roomname

    def chatUpdate(self,roomid,user,inroom):
        if self._usermapping.has_key(toc.normalize(user)):user=self._usermapping[toc.normalize(user)]
        if inroom:
            self.memberJoined(user,self._roomid[roomid])
        else:
            self.memberLeft(user,self,_roomid[roomid])

    def chatHearMessage(self,roomid,user,message):
        if user==self.username: return
        message=dehtml(message)
        if self._usermapping.has_key(toc.normalize(user)):user=self._usermapping[toc.normalize(user)]
        self.receiveGroupMessage(user,self._roomid[roomid],message)

    def chatLeft(self,roomid):
        roomname=self._roomid[roomid]
        if self._chatmapping.has_key(toc.normalize(roomname)):
            del self._chatmapping[toc.normalize(roomname)]
        del self._roomid[roomid]
    
    def writeNewConfig(self):
        self.set_config(self._savedmode,self._savedlist,self._savedpermit,self._saveddeny)

    def addContact(self,contact):
        self.add_buddy([contact])
        try:
            k=self._savedlist.keys()[0]
        except IndexError:
            k="Twisted Buddies"
            self._savedlist[k]=[]
        self._savedlist[k].append(contact)
        self.writeNewConfig()
        self._usermapping[toc.normalize(contact)]=contact
        self.notifyStatusChanged(contact,"Offline")

    def removeContact(self,contact):
        self.del_buddy([contact])
        n=toc.normalize(contact)
        if self._usermapping.has_key(n):del self._usermapping[n]
        for k in self._savedlist.keys():
            for u in range(len(self._savedlist[k])):
                if n==toc.normalize(self._savedlist[k][u]):
                    del self._savedlist[k][u]
                    self.writeNewConfig()
                    return

    def changeStatus(self,newStatus):
        pass # XXX: need to define what newStatus is

    def joinGroup(self,groupname):
        self._chatmapping[toc.normalize(groupname)]=groupname
        self.chat_join(4,groupname)

    def leaveChat(self,groupname):
        for i in self._roomid.keys():
            if self.roomid[i]==groupname:
                self.chat_leave(groupname)
                del self._roomid[i]
                if self._chatmapping.has_key(toc.normalize(groupname)):del self._chatmapping[toc.normalize(groupname)]

    def getGroupMembers(self,groupname):
        #self.receiveGroupMembers([],groupname)
        pass
        
    def directMessage(self,user,message):
        self.say(user,message)

    def groupMessage(self,groupname,message):
        for k in self._roomid.keys():
            if self._roomid[k]==groupname:
                id=k
        if not id: return
        self.chat_say(id,message)
