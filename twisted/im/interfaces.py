from twisted.python.components import Interface

import locals

"""Pan-protocol chat client.

Stability: incendiary, work in progress.
"""

class IAccount(Interface):
    """I represent a user's account with a chat service.

    @cvar gatewayType: Identifies the protocol used by this account.
    @type gatewayType: string
    """

    def __init__(self, accountName, autoLogin, username, password, host, port):
        """
        @type accountName: string
        @param accountName: A name to refer to the account by locally.
        @type autoLogin: boolean
        @type username: string
        @type password: string
        @type host: string
        @type port: integer
        """

    def isOnline(self):
        """Am I online?

        @returntype: boolean
        """

    def logOn(self):
        """Go on-line.

        @returntype: Deferred
        """

    def logOff(self):
        """Sign off.
        """

class IClient(Interface):
    def __init__(self, account, chatui):
        """
        """
        

# Accounts have Protocol components (clients)
# Persons have Conversation components
# Groups have GroupConversation components
# Persons and Groups are associated with specific Accounts
# At run-time, Clients/Accounts are slaved to a User Interface
#   (Note: User may be a bot, so don't assume all UIs are built on gui toolkits)

class IPerson(Interface):
    def isOnline(self):
        """Am I online right now?

        @returntype: boolean
        """

    def getStatus(self):
        """What is my on-line status?

        @returns: L{locals.StatusEnum}
        """

    def getIdleTime(self):
        """
        @returntype: string (XXX: How about a scalar?)
        """

    def sendMessage(self, text, metadata=None):
        """Send a message to this person.
        
        @type text: string
        @type metadata: dict
        """


class IGroup(Interface):
    def setTopic(self, text):
        pass

    def sendGroupMessage(self, text, metadata=None):
        """Send a message to this group.

        @type text: string
        @type metadata: dict
        """

    def leave(self):
        pass
