class PersonState:pass
class Online(PersonState):pass
class Away(PersonState):
    def __init__(self, message):
        self.message = message
class Idle(PersonState):
    def __init__(self, seconds):
        self.seconds = seconds

class IPerson(Interface):
    """
    The generic IM person.
    """

    def getStatus(self):
        """
        Return the current status of this user, or a Deferred that is
        called back with the status.

        possible statuses:

        ( Online(), )
        ( Online(), Away("eating dinner") )
        ( Online(), Away("auto message"), Idle(600) )
        () # offline
        <whatever else ICQ and Jabber support>
        """

    def getInfo(self):
        """
        Return any information that the user has shared over the protocol.

        Returns a Deferred that is called back with a dictionary.  Each key
        represents a piece of information that the user has defined.

        XXX define these fields
        """
    
    def sendMessage(self, message):
        """
        Send a message to this user.

        Returns a Deferred that is called back when the message has been sent.
        """

class IGroup(Interface):
    """
    Represents a group of People.

    Note: any classes that implement this class should also implement the
    tuple methods __setitem__ and __getitem__.  They should take/return
    IPerson implementors.
    """

    def getName(self):
        """
        Returns the name of this group.
        """

class ISendFileTransfer(Interface):
    """
    Implemented if the Person supports having files sent to them.
    """

    def sendFile(self, protocolInstance):
        """
        Send the "file" to the opposite side.  The protocol can be any
        instance supporting IProtocol, or anything that can be adapted
        to that interface.
        """

class IGetFileTransfer(Interface):
    """
    Implemented if the InstantMessangerConnection supports receiving files.
    """

    def getFile(self, protocolInstance):
        """
        Receive the "file" from the opposite side.  protocolInstance is
        something that can be adapted to IProtocol.
        """

class IGroupChat(Interface):
    """
    A generic group chat.
    """

    def getUsers(self):
        """
        Return the users who are currently in the chat room.

        Returns a Deferred that is called back with a list of instances that
        implement IPerson.
        """

    def sendMessage(self, message):
        """
        Send a message to the chat.

        Returns a Deferred that is called back when the message is received.
        """

class IInstantMessageConnection(Interface):
    """
    This represents our connection to an IM service.  It maintains our
    notify/buddy list, lets us change our shared information, privacy
    settings, etc.
    """

    def notifyOnline(self):
        """
        Called when we are online.
        """

    def retrieveNotifyList(self):
        """
        Return the list of users who we're being notified of.

        Returns a Deferred that is called back with a list of
        IGroup implementors.
        """

    def setNotifyList(self, l):
        """
        Sets the list of users we wish to be notified of.

        l is a list of IGroup implementors.

        Returns a Deferred that is called back when it succeeds.
        """

    def setInfo(self, infoDict):
        """
        Set the information we wish to transmit to the world.

        infoDict is a dictionary with keys representing the fields we wish
        to set.

        Returns a Deferred that is called back when this succeeds.
        """

    def getSelf(self):
        """
        Return the IPerson implementer that represents us.
        """

    def retrievePrivacy(self):
        """
        Retrieve the privacy state.

        Returns a Deferred that is called back with one of the following.

        ("all") allow all users to see us
        ("none") allow no users to see us
        ("permit", [list of IPerson implementors]) allow these people to see us
        ("deny",    '') don't allow these people to see us
        ("notifylist") allow the people on our notify list to see us
        """

    def setPrivacy(self, state):
        """
        Set the privacy state.

        See retrievePrivacy() for what state should be.

        Returns a Deferred that will be called back when this succeeds.
        """

    def setStatus(self, statusList):
        """
        Set our status.

        status is a list of PersonStatus subclasses.

        Returns a Deferred that will be called back when this succeeds.
        """
