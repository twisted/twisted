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

import os
import string
import time
from twisted.spread import pb
from twisted.words.ui import gateway
class Conversation:
    def __init__(self,im,gatewayname,target):
        raise NotImplementedError

class ContactList:
    def __init__(self,im):
        raise NotImplementedError

class GroupSession:
    def __init__(self,name,im,gatewayname):
        raise NotImplementedError

class InstanceMessenger:
    """This is the interface between Gateways (protocols) and the windows
    that make up IM.
    """
    def __init__(self):
        self.gateways={}
        self.conversations = {}
        self.groups = {}
        self.cl=None
        self.logging=0
        
    def _log(self,gatewayname,user,text):
        if not self.logging: return
        path=os.path.expanduser("~")
        gatewayname=string.replace(gatewayname," ","")
        user=string.replace(user," ","")
        filename=path+os.sep+"im"+os.sep+gatewayname+"-"+user+".log"
        print filename
        f=open(filename,"a")
        f.write("(%s) %s\n"%(time.asctime(time.localtime(time.time())),text))
        f.close()
        
    def attachGateway(self, gateway):
        if not self.cl:self.cl=ContactList(self)
        self.gateways[gateway.name]=gateway
    
    def detachGateway(self, gatewayname):
        del self.gateways[gatewayname]
    
    def conversationWith(self, gatewayname, target):
        conv = self.conversations.get(gatewayname+target)
        if not conv:
            conv = Conversation(self,gatewayname,target)
            self.conversations[gatewayname+target] = conv
        return conv

    def addContact(self, gatewayname, contact):
        gateway=self.gateways[gatewayname]
        gateway.addContact(contact)

    def removeContact(self, gatewayname,contact):
        gateway=self.gateways[gatewayname]
        gateway.removeContact(contact)
    
    def receiveContactList(self,gatewayname,contacts):
        if not self.cl: self.cl = ContactList(self)
        for contact,status in contacts:
            self.cl.changeContactStatus(gatewayname,contact,status)

    def receiveDirectMessage(self, gatewayname, sender, message):
        # make sure we've started the conversation
        w = self.conversationWith(gatewayname,sender) 
        self._log(gatewayname,sender,"<%s> %s"%(sender,message))
        w.messageReceived(message)

    def notifyStatusChanged(self,gatewayname,contact,newStatus):
        if not self.cl: self.cl=ContactList(self)
        self.cl.changeContactStatus(gatewayname,contact,newStatus)
        self._log(gatewayname,contact,"%s is %s!"%(contact,newStatus))

    def joinGroup(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.joinGroup(group)
        self.groups[gatewayname+group]=GroupSession(group,self,gatewayname)
        self._log(gatewayname,group+".chat","Joined group!")
        
    def leaveGroup(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.leaveGroup(group)
        del self.groups[gatewayname+group]
        self._log(gatewayname,group+".chat","Left group!")

    def getGroupMembers(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.getGroupMembers(group)
    def receiveGroupMembers(self,gatewayname,members,group):
        self.groups[gatewayname+group].receiveGroupMembers(members)
        self._log(gatewayname,group+".chat","Users in group: %s"%members)

    def receiveGroupMessage(self,gatewayname,member,group,message):
        self.groups[gatewayname+group].displayMessage(member,message)
        self._log(gatewayname,group+".chat","<%s> %s"%(member,message))

    def memberJoined(self,gatewayname,member,group):
        self.groups[gatewayname+group].memberJoined(member)
        self._log(gatewayname,group+".chat","%s joined!"%member)

    def memberLeft(self,gatewayname,member,group):
        self.groups[gatewayname+group].memberLeft(member)
        self._log(gatewayname,group+".chat","%s left!"%member)

    def directMessage(self,gatewayname,user,message):
        gateway=self.gateways[gatewayname]
        gateway.directMessage(user,message)
        self._log(gatewayname,user,"<%s> %s"%(gateway.username,message))
    def groupMessage(self,gatewayname,group,message):
        gateway=self.gateways[gatewayname]
        gateway.groupMessage(group,message)
        self._log(gatewayname,group+".chat","<<%s>> %s"%(gateway.username,message))
