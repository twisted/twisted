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
import cPickle
from twisted.spread import pb
from twisted.words.ui import gateways

ERROR,CONNECTIONFAILED,CONNECTIONLOST=range(3) # the error codes
STATUSES=["Offline","Online","Away"]

class Conversation:
    def __init__(self,im,gateway,target):
        """
        represents a conversation with a single user.
        im := the InstanceMessenger that's being used (class InstanceMessenger)
        gateway := the gateway the conversation is over (class Gateway)
        target := the user who the conversation is with (string)
        """
        raise NotImplementedError

    def messageReceived(self,message):
        """
        called when we get a message sent to us.
        message := the message that was sent (string)
        """
        raise NotImplementedError

    def changeName(self,newName):
        """
        called when this user changes their name on the server.
        newName := the users new name (string)
        """
        raise NotImplementedError

class ContactList:
    def __init__(self,im):
        """
        represents the list of users on our contact list. (perhaps more than one
        gateway)
        im := the InstanceMessenger that's being used (class InstanceMessenger)
        """
        raise NotImplementedError

    def changeContactStatus(self,gateway,contact,newStatus):
        """
        change the status of a contact on our list.
        gateway := the gateway the contact is from (class Gateway)
        contact := the username of the contact that changed (string)
        newStatus := the new status (string)
        """
        raise NotImplementedError

    def changeContactName(self,gateway,contact,newName):
        """
        change the name of a contact on our list.  it could be our username as
        well, in which case, the gateway name has probably changed as well.
        gateway := the gateway the contact is from (class Gateway)
        contact := the old name of the contact (string)
        newName := the new name of the contact (string)
        """
        raise NotImplementedError

class GroupSession:
    def __init__(self,im,name,gateway):
        """
        represents a group chat.
        im := the InstanceMesseneger that's being used (class InstanceMessenger)
        name := the name of the group (string)
        gateway := the gateway that's being used (class Gateway)
        """
        raise NotImplementedError
    
    def receiveGroupMembers(self,members):
        """
        called when we receive the list of members already in the group
        members := the names of the current members (list of strings)
        """
        raise NotImplementedError
    
    def receiveGroupMessage(self,member,message):
        """
        called when a member of the group sends a message. note: we /don't/ get
        this call when we send a message.
        member := the member who sent the message (string)
        message := the message (string)
        """
        raise NotImplementedError
    
    def memberJoined(self,member):
        """
        called when a member joins the group.
        member := the member who just joined the group
        """
        raise NotImplementedError
    
    def memberLeft(self,member):
        """
        called when a member leaves the group.
        member := the member who just left the group
        """
        raise NotImplementedError

    def changeMemberName(self,member,newName):
        """
        change the name of a member in the group.  it could be our username as
        well, in which case, the gateway name has probably changed as well.
        member := the old name of the member (string)
        newName := the new name of the member (string)
        """
        raise NotImplementedError
        
def ErrorWindow(error,message):
    """
    displayed when an error occurs.
    error := a short message of the error (good for the title)
    message := a more detailed error message
    """
    raise NotImplementedError

"""
Conversation, ContactList, GroupSession, and ErrorWindow should be overridden by
    GUI programs to implement the various windows, i.e in your client:

import im2
im2.Conversation=MyConversationClass
im2.GroupSession=MyGroupSessionClass
im2.ContactList=MyContactListClass
im2.ErrorWindow=MyErrorWindowClass
"""
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
        self.callbacks={}

    def _log(self,gateway,user,text):
        """
        used to log conversations/chats to a file
        gateway := the gateway the message is from (class Gateway 
        user := the user who sent the message, ends in .chat for groups (string)
        text := the message they sent (string)
        """
        if not self.logging: return
        path=os.path.expanduser("~")
        gatewayname=gateway.username+"-"+gateway.protocol
        user=string.lower(string.replace(user," ",""))
        filename=path+os.sep+"im"+os.sep+gatewayname+"-"+user+".log"
        f=open(filename,"a")
        f.write("(%s) %s\n"%(time.asctime(time.localtime(time.time())),text))
        f.close()
        
    def attachGateway(self, gateway):
        """
        called when a gateway is connected to attach it to the GUI.
        gateway := the gateway to attach (class Gateway)
        """
        self.sendEvent(gateway,"attached")
        if not self.cl:self.cl=ContactList(self)
        self.gateways[gateway.name]=gateway
        gateway.attachIM(self)
    
    def detachGateway(self, gateway):
        """
        called when a gateway wants to detach from the GUI.
        gateway := the gateway to detach (class Gateway) 
        """
        self.sendEvent(gateway,"detached")
        del self.gateways[gateway.name]
        gateway.detachIM()
    
    def conversationWith(self, gateway, target):
        """
        internal function to make sure that a Conversation window is showing.
        gateway := the gateway the conversation is over (class Gateway)
        target := the user the conversation is with (string)
        """
        conv = self.conversations.get(str(gateway)+target)
        if not conv:
            conv = Conversation(self,gateway,target)
            self.conversations[str(gateway)+target] = conv
        return conv

    def endConversation(self, gateway, target):
        """
        internal function to remove the Conversation window.
        gateway := the gateway the conversation was over (class Gateway)
        target := the user the conversation was with (string)
        """
        if self.conversations.has_key(str(gateway)+target):
            del self.conversations[str(gateway)+target]

    def addContact(self, gateway, contact):
        """
        add a contact to the gateways contact list.
        gateway := the gateway to add the contact to (class Gateway) 
        contact := the contact to add to the list (string)
        """
        gateway.addContact(contact)

    def removeContact(self, gateway,contact):
        """
        remove a contact from the gateways contact list.
        gateway := the gateway to remove the contact from (class Gateway)
        contact := the contact to remove from the list (string)
        """
        gateway.removeContact(contact)
    
    def receiveContactList(self,gateway,contacts):
        """
        called when we receive the contact list from a gateway
        gateway := the gateway the list is from (class Gateway) 
        contacts := a list of the contacts (list)
        """
        self.sendEvent(gateway,"receiveContactList",contacts)
        if not self.cl: self.cl = ContactList(self)
        for contact,status in contacts:
            self.cl.changeContactStatus(gateway,contact,status)

    def receiveDirectMessage(self, gateway, sender, message):
        """
        called when we receive a direct message.
        gateway := the gateway the message is from (class Gateway)
        sender := the user who sent it (string)
        message := the message (string)
        """
        if self.sendEvent(gateway,"receiveDirectMessage",sender,message):
            # make sure we've started the conversation
            w = self.conversationWith(gateway,sender) 
            self._log(gateway,sender,"<%s> %s"%(sender,message))
            w.messageReceived(message)

    def notifyStatusChanged(self,gateway,contact,newStatus):
        """
        called when a contact on our contact list changes status.
        gateway := the gateway the contact is on (class Gateway)
        contact := the contact whos status changed (string)
        newStatus := the new status of the contact (string)
        """
        if not self.cl: self.cl=ContactList(self)
        self.sendEvent(gateway,"notifyStatusChanged",contact,newStatus)
        self.cl.changeContactStatus(gateway,contact,newStatus)
        self._log(gateway,contact,"%s is %s!"%(contact,newStatus))

    def notifyNameChanged(self,gateway,contact,newName):
        """
        called when the nickname of a contact we're observing (on contact list,
        in chat room, direct message) changes their name.  we get one of these
        as well if we change our nickname.
        gateway := the gateway the contact is on (class Gateway)
        contact := the old name of the contact (string)
        newName := the new name of the contact (string)
        """
        self.sendEvent(gateway,"notifyNameChanged",contact,newName)
        self.cl.changeContactName(gateway,contact,newName)
        try:
            conv=self.conversations[str(gateway)+contact]
        except KeyError:
            pass
        else:
            conv.changeName(newName)
            del self.conversations[str(gateway)+contact]
            self.conversations[str(gateway)+newName]=conv
        l=len(str(gateway))
        for k in self.groups.keys():
            if k[:l]==str(gateway):
                self.groups[k].changeMemberName(contact,newName)
        self._log(gateway,contact,"%s changed name to %s!"%(contact,newName))

    def joinGroup(self,gateway,group):
        """
        join a group.
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        if self.sendEvent(gateway,"joinGroup",group):
            gateway.joinGroup(group)
            self.groups[str(gateway)+group]=GroupSession(self,group,gateway)
            self._log(gateway,group+".chat","Joined group!")
        
    def leaveGroup(self,gateway,group):
        """
        leave a group
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        if self.sendEvent(gateway,"leaveGroup",group):
            gateway.leaveGroup(group)
            del self.groups[str(gateway)+group]
            self._log(gateway,group+".chat","Left group!")

    def getGroupMembers(self,gateway,group):
        """
        get the members for a group we're in.
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        gateway.getGroupMembers(group)
        
    def receiveGroupMembers(self,gateway,members,group):
        """
        called when we receive the list of group members.
        gateway := the gateway the group is on (class Gateway)
        members := the list of members in the group (list)
        group := the name of the group (string)
        """
        self.sendEvent(gateway,"receiveGroupMembers",members,group)
        self.groups[str(gateway)+group].receiveGroupMembers(members)
        self._log(gateway,group+".chat","Users in group: %s"%members)

    def receiveGroupMessage(self,gateway,member,group,message):
        """
        called when someone sends a message to a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the user who sent the message (string)
        group := the group the message was sent to (string)
        message := the message (string)
        """
        if self.sendEvent(gateway,"receiveGroupMessage",member,group,message):
            self.groups[str(gateway)+group].displayMessage(member,message)
            self._log(gateway,group+".chat","<%s> %s"%(member,message))

    def memberJoined(self,gateway,member,group):
        """
        called when someone joins a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the member who joined the group (string)
        group := the group the member joined (string)
        """
        if self.sendEvent(gateway,"memberJoined",member,group):
            self.groups[str(gateway)+group].memberJoined(member)
            self._log(gateway,group+".chat","%s joined!"%member)

    def memberLeft(self,gateway,member,group):
        """
        called when someone leaves a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the member who left the group (string)
        group := the group the member left (string)
        """
        if self.sendEvent(gateway,"memberLeft",member,group):
            self.groups[str(gateway)+group].memberLeft(member)
            self._log(gateway,group+".chat","%s left!"%member)

    def directMessage(self,gateway,user,message):
        """
        send a direct message to a user.
        gateway := the gateway to send the message over
        user := the user to send the message to (string)
        message := the message to send (string)
        """
        if self.sendEvent(gateway,"directMessage",user,message):
            gateway.directMessage(user,message)
            self._log(gateway,user,"<%s> %s"%(gateway.username,message))
    
    def groupMessage(self,gateway,group,message):
        """
        send a message to a group.
        gateway := the gateway the group is on (class Gateway)
        group := the group to send the message to (string)
        message := the message to send (string)
        """
        if self.sendEvent(gateway,"groupMessage",group,message):
            gateway.groupMessage(group,message)
            self._log(gateway,group+".chat","<<%s>> %s"%(gateway.username,message))

    def connectionFailed(self,gateway,message):
        """
        called when a gateway fails to connect.
        gateway := the gateway that failed to connect (class Gateway)
        message := the reason the connection failed (string)
        """
        if self.sendEvent(gateway,"error",CONNECTIONFAILED,message):
            ErrorWindow("Connection Failed!",message)

    def connectionLost(self,gateway,message):
        """
        called when a gateway loses its connection.
        gateway := the gateway that lost its connection (class Gateway)
        message := the reason the connection was lost (string)
        """
        if self.sendEvent(gateway,"error",CONNECTIONLOST,message):
            ErrorWindow("Connection Lost!",message)

    def addCallback(self,gateway,event,callback):
        """
        add a callback for a gateway, event code, or both.
        gateway := the gateway to add a callback for (class Gateway, or None for
            any gateway)
        event := the event code to add a callback for (string, or None for any 
            code)
        callback := a function to be called when the event is triggered 
            (function)
        """ 
        if self.callbacks.has_key(event):
            self.callbacks[event].append((gateway,callback))
        else:
            self.callbacks[event]=[(gateway,callback)]

    def removeCallback(self,gateway,event,callback):
        """
        remove a callback for a gateway, event code, or both.
        gateway, code, and callback are the values that were passed to
            addCallback()
        """
        if not self.callbacks.has_key(event): return
        self.callbacks[event].remove((gateway,callback))

    def sendEvent(self,gateway,event,*args):
        """
        called when an event is triggered.
        the callback should take:
            im := the IM client (class InstanceMessenger)
            gateway := the gateway that generate the event (class Gateway)
            event := the event code for the event (string)
            *args := the event-specific values are apply()ed to the function
                (tuple)
        if any of the callbacks return "break", then the default action for the 
            event will not happen.
        gateway := the gateway that generated the event (class Gateway)
        event := the event code for the event (string)
        *args := any event-specific values are tossed into here (tuple)
        """
        br=0
        for e in event,None:
            callbacks=self.callbacks.get(event)
            if callbacks:
                for g,c in callbacks:
                    if g in (gateway,None):
                        r=apply(c,(self,gateway,event)+args,{})
                        if r=="break": br=1
        return not br

class Account:
    def __init__(self,gatewayname,options,autologon,savepass):
        """
        A simple class to save the options for an IM account.
        gatewayname := the shortName of the gateway to use (string)
        options := the options to use for makeConnection (dictionary)
        autologon := automatically log this account in? (int)
        savepass := save this password? (int)
        """
        self.gatewayname=gatewayname
        self.options=options
        self.autologon=autologon
        self.savepass=savepass

def getState(file):
    """
    retrieve the state from an open file.
    returns the state as a list of Account objects.
    file := the file to retreive the state from (open file)
    """
    return cPickle.load(file)

def saveState(file,state):
    """
    save the current state to a file.
    file := the file to save the state to (open file)
    state := the current state (list of Account objects)
    """
    for account in state:
        if not account.savepass: # don't save password
            for k in account.options.keys():
                if k[:4]=="pass":
                    del account.options[k]
    cPickle.dump(state,file)

def logonAccount(im,account):
    """
    log on to a given account.
    if not all the options are present, returns the options that are missing.
    im := the InstanceMessenger to connect the account to
        (class InstanceMessenger)
    account := the account to connect (class Account)
    """
    if len(account.options)<len(gateways.__gateways__[account.gatewayname].loginOptions):
        ret=[]
        for foo,key,bar in gateways.__gateways__[account.gatewayname].loginOptions:
            if not account.options.has_key(key):
                ret.append([foo,key,bar])
        return ret
    apply(gateways.__gateways__[account.gatewayname].makeConnection,(im,),account.options)

def logoffAccount(im,account):
    """
    log off a given account
    im := the InstanceMessenger to disconnect the account from
        (class InstanceMessenger)
    account := the account to disconnect (class Account)
    """
    for g in im.gateways.values():
        if g.logonUsername==account.options["username"] and g.protocol==account.gatewayname:
            im.addCallback(g,"error",_handleDisconnect)
            g.loseConnection()

def _handleDisconnect(im,gateway,event,code,message):
    im.removeCallback(gateway,event,_handleDisconnect)
    if code==CONNECTIONLOST: return "break"
