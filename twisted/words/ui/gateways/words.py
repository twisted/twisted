
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

from twisted.internet import tcp
from twisted.spread import pb
from twisted.words.service import statuses
from twisted.words.ui import gateway

loginOptions=[
    ["text","Username","username","guest"],
    ["password","Password","password","guest"],
    ["text","Service","service","twisted.words"],
    ["text","Hostname","server","localhost"],
    ["text","Port #","port",str(pb.portno)]]

shortName="Words"
longName="Twisted.Words"

class makeConnection:
    def __init__(self,im,server=None,port=None,username=None,password=None,service=None):
        self.im=im
        self.service=service
        self.username=username
        self.attached=0
        self.ref=WordsGateway(username)
        pb.connect(
            server, int(port),
            username, password,
            service, username, # need to fix this, maybe?
            self.ref, 60
            ).addCallbacks(self.pbCallback, self.connectionFailed)
        self.connected=1

    def connectionFailed(self,tb):
        if self.connected:
            self.im.send(self,"error",message="Connection Failed!")
            if self.attached:
                self.ref.detachIM()
        self.connected=0

    def connectionLost(self):
        print "foo"
        if self.connected:
            self.im.send(self,"error",message="Connection Lost.")
            if self.attached:
                self.ref.detachIM()
        self.connected=0
    
    def pbCallback(self,perspective):
        perspective.broker.notifyOnDisconnect(self.connectionLost)
        self.ref.attachIM(self.im)
        self.ref.connected(perspective)
        self.ref.b=perspective.broker
        self.attached=1
        
class WordsGateway(gateway.Gateway,pb.Referenceable):
    """This is the interface between IM and a twisted.words service
    """
    protocol=shortName

    def __init__(self,username):
        gateway.Gateway.__init__(self)
        self.username=username
        self.logonUsername=username
        self.name="%s (%s)"%(self.username,self.protocol)
        self._connected=0
        self._list=()
        self._changes=[]

    def loseConnection(self):
        self.b.transport.loseConnection()
        
#The PB interface.
    def connected(self, perspective):
        self.remote = perspective
        self._connected=1
        if self._list:
            self.receiveContactList(self._list)
            del self._list
        if self._changes:
            for contact,status in self._changes:
                self.notifyStatusChanged(contact,status)
            del self._changes
    
    def remote_receiveContactList(self,contacts):
        c=[]
        for contact,status in contacts:
            status=statuses[status]
            c.append((contact,status))
        if self._connected:self.receiveContactList(self,c)
        else: self._list=c
    
    def remote_notifyStatusChanged(self,contact,newStatus):
        #print contact,"changed status to",newStatus
        if self._connected:self.notifyStatusChanged(contact,statuses[newStatus])
        else: self._changes.append((contact,statuses[newStatus]))

    def remote_receiveDirectMessage(self,sender,message):
        self.receiveDirectMessage(sender,message)
        
    def remote_receiveGroupMembers(self,members,group):
        self.receiveGroupMembers(members,group)
    
    def remote_receiveGroupMessage(self,sender,group,message):
        self.receiveGroupMessage(sender,group,message)
        
    def remote_memberJoined(self,member,group):
        self.memberJoined(member,group)
    
    def remote_memberLeft(self,member,group):
        self.memberLeft(member,group)

    def event_addContact(self,contact):
        self.remote.addContact(contact)
    
    def event_removeContact(self,contact):
        self.remote.removeContact(contact)
    
    def event_changeStatus(self,status):
        self.remote.changeStatus(statuses.index(status))

    def event_joinGroup(self,group):
        self.remote.joinGroup(group)
        self.joinedGroup(group)

    def leaveGroup(self,group):
        self.remote.leaveGroup(group)
        self.leftGroup(group)

    def event_getGroupMembers(self,group):
        self.remote.getGroupMembers(group).addCallbacks(lambda x: x, lambda tb,s=self,g=group:s.noGroupMembers(g))

    def noGroupMembers(self,group):
        self.receiveGroupMembers([],group)

    def event_directMessage(self,user,message):
        self.remote.directMessage(user,message)

    def event_groupMessage(self,group,message):
        self.remote.groupMessage(group,message)

groupExtras=[]

conversationExtras=[]

contactListExtras=[]
