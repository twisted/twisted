
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

loginOptions=[["Username","username","guest"],["Password","password","guest"],["Service","service","twisted.words"],["Hostname","server","localhost"],["Port #","port",str(pb.portno)]]


class makeConnection:
    def __init__(self,im,server=None,port=None,username=None,password=None,service=None):
        self.im=im
        b=pb.Broker()
        b.requestIdentity(username,password,callback=self.gotIdentity,errback=self.notConnected)
        self.username=username
        self.service=service
        tcp.Client(server,int(port),b)

    def notConnected(self,tb):
        print "NOT CONNECTED!"
        print tb
    
    def gotIdentity(self,identity):
        self.ref=WordsGateway(self.im)
        self.ref.username=self.username
        identity.attach(self.service,self.username,self.ref,pbcallback=self.pbCallback)

    def pbCallback(self,perspective):
        self.ref.connected(perspective)
        self.im.attachGateway(self.ref)
        
class WordsGateway(gateway.Gateway,pb.Referenced):
    """This is the interface between IM and a twisted.words service
    """
    protocol="Words"
    def __init__(self,im):
        gateway.Gateway.__init__(self,im)
        self._connected=0
        self._list=()
        self._changes=[]
        
#The PB interface.
    def connected(self, perspective):
        self.remote = perspective
        self.name="%s (%s)"%(self.username,self.protocol)
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

    def addContact(self,contact):
        self.remote.addContact(contact)
    
    def removeContact(self,contact):
        self.remote.removeContact(contact)
    
    def changeStatus(self,newStatus):
        self.remote.changeStatus(newStatus)

    def joinGroup(self,group):
        self.remote.joinGroup(group)

    def leaveGroup(self,group):
        self.remote.leaveGroup(group)

    def getGroupMembers(self,group):
        self.remote.getGroupMembers(group,pberrback=lambda tb,s=self,g=group:s.noGroupMembers(g))

    def noGroupMembers(self,group):
        self.receiveGroupMembers([],group)

    def directMessage(self,user,message):
        self.remote.directMessage(user,message)

    def groupMessage(self,group,message):
        self.remote.groupMessage(group,message)
