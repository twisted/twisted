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

import cPickle
import string

from twisted.words.ui import gateways

STATUSES=["Online","Away"]

def send_only(func,**kw):
    if hasattr(func,"im_self"):
        kw["self"]=func.im_self
        func=func.im_func
    if func.func_code.co_flags & 0x0008: # CO_VARKEYWORDS
        return apply(func,[],kw)
    keys={}
    for k in func.func_code.co_varnames[:func.func_code.co_argcount]:
        keys[k]=kw[k]
    return apply(func,[],keys)

class InstanceMessenger:
    def __init__(self):
        self.__connected={}

    def connect(self,function,event_name=None,gateway=None):
        if not self.__connected.has_key(gateway):
            self.__connected[gateway]={}
        if not self.__connected[gateway].has_key(event_name):
            self.__connected[gateway][event_name]=[]
        self.__connected[gateway][event_name].append(function)

    def connect_class(self,instance,gateway=None):
        for k,v in instance.__class__.__dict__.items():
            if k[:6]=="event_":
                event_name=k[6:]
                function=getattr(instance,k)
                self.connect(function,event_name,gateway)

    def disconnect(self,function,event_name=None,gateway=None):
        self.__connected[gateway][event_name].remove(function)

    def disconnect_class(self,instance,gateway=None):
        for n in dir(instance):
            if n[:6]=="event_":
                event_name=n[6:]
                function=getattr(instance,n)
                self.disconnect(function,event_name,gateway)

    def send(self,gateway,event_name,**kw):
        kw["gateway"]=gateway
        kw["event_name"]=event_name
        if gateway==None: # special case, send for every gateway
            for k in self.__connected.keys():
                if k:
                    self.__send(k,event_name,kw)
            return
        r=self.__send(gateway,event_name,kw) # specific
        if not r: r=self.__send(None,event_name,kw) # not gateway specific
        if not r: r=self.__send(gateway,None,kw) # not event specific
        if not r: self.__send(None,None,kw) # not anything specific

    def __send(self,gateway,event_name,kw):
        if not self.__connected.has_key(gateway): return
        if not self.__connected[gateway].has_key(event_name): return
        functions=self.__connected[gateway][event_name]
        for func in functions:
            result=apply(send_only,[func],kw)
            if result=="break": return 1

class InstanceMessengerGUI:
    """This is the interface between InstanceMessenger events and the windows
    that make up the interface.
    """
    def __init__(self, im,Conversation, ContactList, GroupSession, ErrorWindow):
        self.Conversation, self.ContactList, self.GroupSession, self.ErrorWindow = \
            Conversation, ContactList, GroupSession, ErrorWindow
        self.im=im
        self.im.connect_class(self,None)
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
        try:
            f=open(filename,"a")
        except IOError:
            f=open(filename,"w")
        f.write("(%s) %s\n"%(time.asctime(time.localtime(time.time())),text))
        f.close()
        
    def event_attach(self, gateway):
        """
        called when a gateway is connected to attach it to the GUI.
        gateway := the gateway to attach (class Gateway)
        """
        if not self.cl:self.cl=self.ContactList(self)
        self.gateways[gateway.name]=gateway
        #gateway.attachIM(self.im)
    
    def event_detach(self, gateway):
        """
        called when a gateway wants to detach from the GUI.
        gateway := the gateway to detach (class Gateway) 
        """
        del self.gateways[gateway.name]
   
    def event_receiveContactList(self,gateway,contacts):
        """
        called when we receive the contact list from a gateway
        gateway := the gateway the list is from (class Gateway) 
        contacts := a list of the contacts (list)
        """
        if not self.cl: self.cl = self.ContactList(self)
        for contact,status in contacts:
            self.cl.changeContactStatus(gateway,contact,status)

    def event_receiveDirectMessage(self, gateway, user, message):
        """
        called when we receive a direct message.
        gateway := the gateway the message is from (class Gateway)
        sender := the user who sent it (string)
        message := the message (string)
        """
        # make sure we've started the conversation
        w = self.conversationWith(gateway,user) 
        w.messageReceived(message)

    def event_statusChanged(self,gateway,contact,status):
        """
        called when a contact on our contact list changes status.
        gateway := the gateway the contact is on (class Gateway)
        contact := the contact whos status changed (string)
        status := the new status of the contact (string)
        """
        if not self.cl: self.cl=self.ContactList(self)
        self.cl.changeContactStatus(gateway,contact,status)
        conv=self.conversations.get(str(gateway)+contact)
        if conv:
            conv.changeStatus(status)

    def event_nameChanged(self,gateway,contact,name):
        """
        called when the nickname of a contact we're observing (on contact list,
        in chat room, direct message) changes their name.  we get one of these
        as well if we change our nickname.
        gateway := the gateway the contact is on (class Gateway)
        contact := the old name of the contact (string)
        name := the new name of the contact (string)
        """
        self.cl.changeContactName(gateway,contact,name)
        try:
            conv=self.conversations[str(gateway)+contact]
        except KeyError:
            pass
        else:
            conv.changeName(name)
            del self.conversations[str(gateway)+contact]
            self.conversations[str(gateway)+name]=conv
        l=len(str(gateway))
        for k in self.groups.keys():
            if k[:l]==str(gateway):
                self.groups[k].changeMemberName(contact,name)

    def event_joinedGroup(self,gateway,group):
        self.groups[str(gateway)+group]=self.GroupSession(self,group,gateway)

    def event_leftGroup(self,gateway,group):
        try:
            del self.groups[str(gateway)+group]
        except KeyError:
            pass
      
    def event_receiveGroupMembers(self,gateway,members,group):
        """
        called when we receive the list of group members.
        gateway := the gateway the group is on (class Gateway)
        members := the list of members in the group (list)
        group := the name of the group (string)
        """
        try:
            self.groups[str(gateway)+group].receiveGroupMembers(members)
        except KeyError:
            pass

    def event_receiveGroupMessage(self,gateway,member,group,message):
        """
        called when someone sends a message to a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the user who sent the message (string)
        group := the group the message was sent to (string)
        message := the message (string)
        """
        try:
            self.groups[str(gateway)+group].receiveGroupMessage(member,message)
        except KeyError:
            pass

    def event_memberJoined(self,gateway,member,group):
        """
        called when someone joins a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the member who joined the group (string)
        group := the group the member joined (string)
        """
        try:
            self.groups[str(gateway)+group].memberJoined(member)
        except KeyError:
            pass

    def event_memberLeft(self,gateway,member,group):
        """
        called when someone leaves a group we're in.
        gateway := the gateway the group is on (class Gateway)
        member := the member who left the group (string)
        group := the group the member left (string)
        """
        try:
            self.groups[str(gateway)+group].memberLeft(member)
        except KeyError:
            pass

    def event_error(self,gateway,message):
        """
        called when an error occurs.
        gateway := the gateway that failed to connect (class Gateway)
        message := the reason the connection failed (string)
        """
        
        self.ErrorWindow(message,message)

    # methods that call events
    def addContact(self, gateway, user):
        """
        add a contact to the gateways contact list.
        gateway := the gateway to add the contact to (class Gateway) 
        user := the contact to add to the list (string)
        """
        self.im.send(gateway,"addContact",contact=user)

    def removeContact(self, gateway, user):
        """
        remove a contact from the gateways contact list.
        gateway := the gateway to remove the contact from (class Gateway)
        user := the contact to remove from the list (string)
        """
        self.im.send(gateway,"removeContact",contact=user)

    def changeStatus(self,status):
        self.im.send(None,"changeStatus",status=status)

    def joinGroup(self,gateway,group):
        """
        join a group.
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        self.im.send(gateway,"joinGroup",group=group)

    def leaveGroup(self,gateway,group):
        """
        leave a group
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        self.im.send(gateway,"leaveGroup",group=group)

    def getGroupMembers(self,gateway,group):
        """
        get the members for a group we're in.
        gateway := the gateway the group is on (class Gateway)
        group := the name of the group (string)
        """
        self.im.send(gateway,"getGroupMembers",group=group)

    def directMessage(self,gateway,user,message):
        """
        send a direct message to a user.
        gateway := the gateway to send the message over
        user := the user to send the message to (string)
        message := the message to send (string)
        """
        self.im.send(gateway,"directMessage",user=user,message=message)
    
    def groupMessage(self,gateway,group,message):
        """
        send a message to a group.
        gateway := the gateway the group is on (class Gateway)
        group := the group to send the message to (string)
        message := the message to send (string)
        """
        self.im.send(gateway,"groupMessage",group=group,message=message)

    # convinence function
    def conversationWith(self, gateway, target):
        """
        internal function to make sure that a Conversation window is showing.
        gateway := the gateway the conversation is over (class Gateway)
        target := the user the conversation is with (string)
        """
        conv = self.conversations.get(str(gateway)+target)
        if not conv:
            conv = self.Conversation(self,gateway,target)
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

    def changeStatus(self,newState):
        """
        called when this user changes their status.
        newState := the users new state (string)
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

# classes and functions to handle IM accounts
# XXX: this could be done better
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
                lo=gateway.__gateways__[k].loginOptions
                for type,foo,name,bar in lo:
                    if name==k and type=="password":
                        del(account.options[k])
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
    apply(gateways.__gateways__[account.gatewayname].makeConnection,(im.im,),account.options)

def logoffAccount(im,account):
    """
    log off a given account
    im := the InstanceMessenger to disconnect the account from
        (class InstanceMessenger)
    account := the account to disconnect (class Account)
    """
    for g in im.gateways.values():
        if g.logonUsername==account.options["username"] and g.protocol==account.gatewayname:
            im.im.connect(_handleDisconnect,"error",g)
            g.loseConnection()

def _handleDisconnect(gateway,message):
    gateway.im.disconnect(_handleDisconnect,"error",gateway)
    return "break"

# misc. functions
def nickComplete(start,users):
    lstart=string.lower(start)
    l=list(users)
    ll=map(string.lower,l)
    if lstart in ll:
        return l[ll.index(lstart)]
    matches=[]
    for u in ll:
        if len(u)>len(lstart) and u[:len(lstart)]==lstart:
            matches.append(u)
    if len(matches)==1:
        return l[ll.index(matches[0])]
    elif matches==[]:
        return
    longestmatch=matches[0]
    for u in matches:
        if len(u)>len(longestmatch):
            u=u[:len(longestmatch)]
        c=0
        while c<len(longestmatch) and longestmatch[c]==u[c]:
            c=c+1
        longestmatch=longestmatch[:c]
    return matches, longestmatch
