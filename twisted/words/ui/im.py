
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

from twisted.spread import pb
class Conversation:
    def __init__(self,im,target):
        raise NotImplementedError
class ContactList:
    def __init__(self,im):
        raise NotImplementedError
class InstanceMessenger(pb.Referenced):
    """This is a broker between the PB broker and the various windows
    that make up InstanceMessenger."""
    def __init__(self):
        self.conversations = {}
        self.groups = {}

    def conversationWith(self, target):
        conv = self.conversations.get(target)
        if not conv:
            conv = Conversation(self, target)
            self.conversations[target] = conv
        return conv

#The PB interface.
    def connected(self, perspective):
        #self.name=lw.username.get_text()
        #lw.hide()
        self.remote = perspective

    def remote_receiveContactList(self,contacts):
        #print 'got contacts'
        self.cl = ContactList(self)
        for contact,status in contacts:
            self.cl.changeContactStatus(contact,status)

    def remote_receiveDirectMessage(self, sender, message):
        #make sure we've started the conversation
        w = self.conversationWith(sender) 
        w.messageReceived(message)

    def remote_notifyStatusChanged(self,contact,newStatus):
        #print contact,"changed status to",newStatus
        self.cl.changeContactStatus(contact,newStatus)


    def remote_receiveGroupMessage(self,member,group,message):
        self.groups[group].displayMessage(member,message)

    def remote_memberJoined(self,member,group):
        self.groups[group].memberJoined(member)

    def remote_memberLeft(self,member,group):
        self.groups[group].memberLeft(member)
