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
class InstanceMessenger(pb.Referenced):
    """This is a broker between the PB broker and the various windows
    that make up InstanceMessenger."""
    def __init__(self):
        self.gateways={}
        self.conversations = {}
        self.groups = {}
        self.cl=None
        
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
        w.messageReceived(message)

    def notifyStatusChanged(self,gatewayname,contact,newStatus):
        if not self.cl: self.cl=ContactList(self)
        self.cl.changeContactStatus(gatewayname,contact,newStatus)

    def joinGroup(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.joinGroup(group)
        self.groups[gatewayname+group]=GroupSession(group,self,gatewayname)
        
    def leaveGroup(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.leaveGroup(group)
        del self.groups[gatewayname+group]

    def getGroupMembers(self,gatewayname,group):
        gateway=self.gateways[gatewayname]
        gateway.getGroupMembers(group)
    def receiveGroupMembers(self,gatewayname,members,group):
        self.groups[gatewayname+group].receiveGroupMembers(members)

    def receiveGroupMessage(self,gatewayname,member,group,message):
        self.groups[gatewayname+group].displayMessage(member,message)

    def memberJoined(self,gatewayname,member,group):
        self.groups[gatewayname+group].memberJoined(member)

    def memberLeft(self,gatewayname,member,group):
        self.groups[gatewayname+group].memberLeft(member)

    def directMessage(self,gatewayname,user,message):
        gateway=self.gateways[gatewayname]
        gateway.directMessage(user,message)
    
    def groupMessage(self,gatewayname,group,message):
        gateway=self.gateways[gatewayname]
        gateway.groupMessage(group,message)
