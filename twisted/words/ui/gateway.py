
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

shortName=None
longName=None
"""
shortName and longName are the short and long names (respectively) for this
protocol.
"""

loginOptions=[]
"""
loginOptions is a list of 3-lists, of the form: 
    [<GUI name>,<option name>,<default value>]
it contains all the options needed to log the gateway in. an example:
    [ ["Username","username","my_username"],
      ["Password","password","my_password"],
      ["Server","server","localhost"],
      ["Port #","port","8000"] ]
      
the GUI names are used in dialog boxes to get the value.
the option names are used in the call to makeConnection().
the default values are used in dialog boxes to show the user what they should
enter.
"""

def makeConnection(im,**kw):
    """
    makeConnection is called from a GUI.  it is given the option names from 
    loginOptions as keyword arguments.  the function then logs the protocol in,
    and attaches it to the InstanceMessenger instance given as the first
    argument.
    """
    raise NotImplementedError

class Gateway:
    """
    This is the interface between a protocol (twisted.words, TOC, etc.) and 
    InstanceMessenger.
    """
    protocol=None # the name for the protocol this implements, gets set to the
                  # short name
    
    def __init__(self):
        """
        Initalize the Gateway instance.
        """
        self.name=None # a unique identifier of (username,protocol)
    
    def attachIM(self,im):
        """
        attach us to an InstanceMessenger.
        im := the InstanceMessenger to attach us to
        """
        self.im=im

    def detachIM(self):
        """
        detach us from an InstanceMessenger.
        """
        self.im=None

    def addContact(self,contact):
        """
        add the given contact to the users contact list.
        contact := the username to add to the contact list
        """
        raise NotImplementedError # XXX: override for gateway

    def removeContact(self,contact):
        """
        remove the given contact from the users contact list.
        contact := the username to remove from the contact list
        """
        raise NotImplementedError # XXX: override for gateway
    
    def receiveContactList(self,contacts):
        """
        called when the contact list is received.
        contacts := a list of the contacts on the contact list
        """
        self.im.receiveContactList(self,contacts)

    def receiveDirectMessage(self, sender, message):
        """
        called when someone sends us a message.
        sender := the user who sent the message
        message := the actual message
        """
        self.im.receiveDirectMessage(self,sender,message)
    
    def changeStatus(self, newStatus):
        """
        change the status for the user.
        newStatus := string for the new status (currently, one of: )
            ["Online","Offline","Away"] 
        """
        raise NotImplementedError # XXX: override for gateway

    def notifyStatusChanged(self,contact,newStatus):
        """
        called when the status of a user on our contact list changes.
        contact := the user whos status changed
        newStatus := their current status, one of ["Online","Offline","Away"]
        """
        self.im.notifyStatusChanged(self,contact,newStatus)
        
    def notifyNameChanged(self,contact,newName):
        """
        called when the nickname of a contact we're observing (on contact list,
        in chat room, direct message) changes their name.  we get one of these
        as well if we change our nickname.
        contact := the /old/ contact name (string)
        newName := the new contact name (string)
        """
        self.im.notifyNameChanged(self,contact,newName)

    def joinGroup(self,group):
        """
        join a group.
        if this method returns true, we are already in the group, and shouldn't
        recreate the window.
        group := the name of the group to join
        """
        raise NotImplementedError # XXX: override for gateway

    def leaveGroup(self,group):
        """
        leave a group.
        group := the name of the group to leave
        """
        raise NotImplementedError # XXX: override for gateway

    def getGroupMembers(self,group):
        """
        ask for the members of a group we are in.
        group := the name of the group we want the members for
        """
        raise NotImplementedError # XXX: override for gateway

    def receiveGroupMembers(self,members,group):
        """
        called when we receive the members for a group.
        members := a list of users in the group
        group := the name of the group
        """
        self.im.receiveGroupMembers(self,members,group)

    def receiveGroupMessage(self,member,group,message):
        """
        called when a message is sent to the group.
        member := the user who sent the message
        group := the group the message was sent to
        message := the actual message
        """
        self.im.receiveGroupMessage(self,member,group,message)

    def memberJoined(self,member,group):
        """
        called when a member joins a group we are in.
        member := the member who joined
        group := the group they joined
        """
        self.im.memberJoined(self,member,group)

    def memberLeft(self,member,group):
        """
        called when a member leaves a group we are in.
        member := the member who left
        group := the group they left
        """
        self.im.memberLeft(self,member,group)

    def directMessage(self,recipientName,message):
        """
        send a direct message to recipientName.
        recipientName := the user to send the message to
        message := the message to send them
        """
        raise NotImplementedError # XXX: override for gateway

    def groupMessage(self,groupName,message):
        """
        send a message to the group groupName.
        groupName := the group to send the message to
        message := the message to send
        """
        raise NotImplementedError # XXX: override for gateway

    
groupExtras=[]
"""
groupExtras is a list of extra options for a group window for this gateway.
each extra is a list:
    [extraName (string), functionToCall (function)]
extraName is the name of the extra on the menu.
functionToCall is what gets called when the extra is selected.  it takes:
    im := the IM client to use (class InstanceMessenger)
    gateway := the gateway to use (class Gateway)
    group := the name of the group (string)
    currenttext := the text currently in the input box (string)
    users := any users currently selected in the userlist box (list)
it returns:
    the text to set the input box to (string)
"""

conversationExtras=[]
"""
conversationExtras is a list of extra options for a conversation window for
this gateway.
each extra is a list:
    [extraName (string), functionToCall (function)]
extraName is the name of the extra on the menu.
functionToCall is what gets called when the extra is selected.  it takes:
    im := the IM client to use (class InstanceMessenger)
    gateway := the gateway to use (class Gateway)
    user := the name of the user the conversation is with (string)
    currenttext := the text currently in the input box (string)
it returns:
    the text to set the input box to (string)
"""

contactListExtras=[]
"""
contactListExtras is a list of extra options that belong on the contact list.
each extra is a list:
    [extraName (string), functionToCall (function)]
extraName is the name of the extra on the menu.
functionToCall is what gets called when the extra is selected.  it takes:
    im := the IM client to use (class InstanceMessenger)
    gateway := the gateway to use (class Gateway)
    user := the name of the currently selected user, or None if none is selected
        for this gateway (string|None)
    userstate := the state of that user, or None if user is None (string|None)
"""
