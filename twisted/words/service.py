
# System Imports
import md5
import string

# Twisted Imports
from twisted.spread import pb
from twisted import copyright

# Status "enumeration"
OFFLINE = 0
ONLINE  = 1
AWAY = 2

class Participant(pb.Cached, pb.Perspective):
    def __init__(self, name, password, service):
        self.name = name
        self.service = service
        self.password = md5.new(password).digest()
        self.status = OFFLINE
        self.contacts = []
        self.groups = []
        self.client = None


    def getStateToCopyFor(self, other):
        assert other in self.contacts,\
               "Non-contacts should not be able to get direct references to each other."
        return {"name": self.name,
                "status": self.status,
                "remote": pb.Proxy(other, self)}

    def proxy_receiveMessage(self, other, message):
        self.receiveMessage(other, None, message)

    def attached(self, client):
        print "participant %s attached to the service" % self.name
        self.client = client
        client.receiveContactList(self.contacts)
        self.changeStatus(ONLINE)

    def changeStatus(self, newStatus):
        for contact in self.contacts:
            contact.notifyStatusChanged(self, newStatus)

    def notifyStatusChanged(self, contact, newStatus):
        if self.client:
            self.client.notifyStatusChanged(contact, newStatus)

    def detached(self, client):
        self.client = None
        if self.groups:
            for group in self.groups:
                group.removeMember(self)
        self.changeStatus(OFFLINE)

    def addContact(self, contactName):
        # TODO: make this consentual
        contact = self.service.getPerspectiveNamed(contactName)
        self.contacts.append(contact)
        if contact is not self:
            contact.contacts.append(self)

    def joinGroup(self, name):
        remote = self.remote
        group = self.service.getGroup(name)
        group.addMember(self)
        self.groups.append(self)

    def leaveGroup(self, group):
        group.removeMember(self)

    def receiveMessage(self, sender, group, message):
        self.remote.receiveMessage(sender, group, message)

    def memberJoined(self, member, group):
        self.remote.memberJoined(member, group)

    def memberLeft(self, member, group):
        self.remote.memberLeft(member, group)

    def sendMessage(self, recipient, message):
        recipient.receiveMessage(self, recipient, message)

    # Establish remote protocol for PB.
    perspective_joinGroup = joinGroup
    perspective_sendMessage = sendMessage
    perspective_addContact = addContact


class Group(pb.Cached):
    def __init__(self, name):
        self.name = name
        self.members = []

    def getStateToCopyFor(self, participant):
        assert participant in self.members, "illegal copy of group"
        return {'name':    self.name,
                'members': self.members,
                'remote':  pb.Proxy(participant, self)}

    def addMember(self, participant):
        for member in self.members:
            member.memberJoined(participant)
        self.members.append(participant)

    def removeMember(self, participant):
        self.members.remove(participant)
        for member in self.members:
            member.memberLeft(participant)


class Service(pb.Service):
    """I am a chat service.
    """

    allowGuests = 1
    
    def __init__(self):
        self.participants = {}
        self.groups = {}

    def getGroup(self, name):
        return self.groups[name]

    def addParticipant(self, name, password):
        if not self.participants.has_key(name):
            print "Created New Participant: %s" % name
            p = Participant(name, password, self)
            self.participants[name] = p
            return p

    def getPassword(self, name):
        return self.getPerspectiveNamed(name).password

    def getPerspectiveNamed(self, name):
        if self.allowGuests:
            return (self.participants.get(name)
                    or self.addParticipant(name, "guest"))
        else:
            return self.participants[name]


