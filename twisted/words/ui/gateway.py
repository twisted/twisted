
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

class Gateway:
    """This is the interface between a protocol (twisted.words, TOC, etc.) and IM."""
    protocol=None # the name for the protocol this implements
    def __init__(self,im):
        self.im=im
        self.name=None
    
    def addContact(self,contact):
        pass # XXX: override for gateway

    def removeContact(self,contact):
        pass # XXX: override for gateway
    
    def receiveContactList(self,contacts):
        self.im.receiveContactList(self.name,contacts)

    def receiveDirectMessage(self, sender, message):
        self.im.receiveDirectMessage(self.name,sender,message)
    
    def changeStatus(self, newStatus):
        pass # XXX: override for gateway

    def notifyStatusChanged(self,contact,newStatus):
        self.im.notifyStatusChanged(self.name,contact,newStatus)

    def joinGroup(self,group):
        pass # XXX: override for gateway

    def leaveGroup(self,group):
        pass # XXX: override for gateway

    def getGroupMembers(self,group):
        pass # XXX: override for gateway

    def receiveGroupMembers(self,members,group):
        self.im.receiveGroupMembers(self.name,members,group)

    def receiveGroupMessage(self,member,group,message):
        self.im.receiveGroupMessage(self.name,member,group,message)

    def memberJoined(self,member,group):
        self.im.memberJoined(self.name,member,group)

    def memberLeft(self,member,group):
        self.im.memberLeft(self.name,member,group)

    def directMessage(self,recipientName,message):
        pass # XXX: override for gateway

    def groupMessage(self,groupName,message):
        pass # XXX: override for gateway

    
