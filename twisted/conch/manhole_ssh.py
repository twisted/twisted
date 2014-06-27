# -*- test-case-name: twisted.conch.test.test_manhole -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
insults/SSH integration support.

@author: Jp Calderone
"""

from zope.interface import implementer

from twisted.conch import avatar, interfaces as iconch, error as econch
from twisted.conch.ssh import factory, keys, session
from twisted.python import components

from twisted.conch.insults import insults

class _Glue:
    """A feeble class for making one attribute look like another.

    This should be replaced with a real class at some point, probably.
    Try not to write new code that uses it.
    """
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        raise AttributeError(self.name, "has no attribute", name)

class TerminalSessionTransport:
    def __init__(self, proto, chainedProtocol, avatar, width, height):
        self.proto = proto
        self.avatar = avatar
        self.chainedProtocol = chainedProtocol

        protoSession = self.proto.session

        self.proto.makeConnection(
            _Glue(write=self.chainedProtocol.dataReceived,
                  loseConnection=lambda: avatar.conn.sendClose(protoSession),
                  name="SSH Proto Transport"))

        def loseConnection():
            self.proto.loseConnection()

        self.chainedProtocol.makeConnection(
            _Glue(write=self.proto.write,
                  loseConnection=loseConnection,
                  name="Chained Proto Transport"))

        # XXX TODO
        # chainedProtocol is supposed to be an ITerminalTransport,
        # maybe.  That means perhaps its terminalProtocol attribute is
        # an ITerminalProtocol, it could be.  So calling terminalSize
        # on that should do the right thing But it'd be nice to clean
        # this bit up.
        self.chainedProtocol.terminalProtocol.terminalSize(width, height)



@implementer(iconch.ISession)
class TerminalSession(components.Adapter):
    transportFactory = TerminalSessionTransport
    chainedProtocolFactory = insults.ServerProtocol

    def getPty(self, term, windowSize, attrs):
        self.height, self.width = windowSize[:2]

    def openShell(self, proto):
        self.transportFactory(
            proto, self.chainedProtocolFactory(),
            iconch.IConchUser(self.original),
            self.width, self.height)

    def execCommand(self, proto, cmd):
        raise econch.ConchError("Cannot execute commands")

    def closed(self):
        pass

class TerminalUser(avatar.ConchUser, components.Adapter):
    def __init__(self, original, avatarId):
        components.Adapter.__init__(self, original)
        avatar.ConchUser.__init__(self)
        self.channelLookup['session'] = session.SSHSession

class TerminalRealm:
    userFactory = TerminalUser
    sessionFactory = TerminalSession

    transportFactory = TerminalSessionTransport
    chainedProtocolFactory = insults.ServerProtocol

    def _getAvatar(self, avatarId):
        comp = components.Componentized()
        user = self.userFactory(comp, avatarId)
        sess = self.sessionFactory(comp)

        sess.transportFactory = self.transportFactory
        sess.chainedProtocolFactory = self.chainedProtocolFactory

        comp.setComponent(iconch.IConchUser, user)
        comp.setComponent(iconch.ISession, sess)

        return user

    def __init__(self, transportFactory=None):
        if transportFactory is not None:
            self.transportFactory = transportFactory

    def requestAvatar(self, avatarId, mind, *interfaces):
        for i in interfaces:
            if i is iconch.IConchUser:
                return (iconch.IConchUser,
                        self._getAvatar(avatarId),
                        lambda: None)
        raise NotImplementedError()

class ConchFactory(factory.SSHFactory):
    publicKey = 'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3/c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHRivcJSkbh/C+BR3utDS555mV'

    publicKeys = {
        'ssh-rsa' : keys.Key.fromString(publicKey)
    }
    del publicKey

    privateKey = """-----BEGIN RSA PRIVATE KEY-----
MIIByAIBAAJhAK8ycfDmDpyZs3+LXwRLy4vA1T6yd/3PZNiPwM+uH8Yx3/YpskSW
4sbUIZR/ZXzY1CMfuC5qyR+UDUbBaaK3Bwyjk8E02C4eSpkabJZGB0Yr3CUpG4fw
vgUd7rQ0ueeZlQIBIwJgbh+1VZfr7WftK5lu7MHtqE1S1vPWZQYE3+VUn8yJADyb
Z4fsZaCrzW9lkIqXkE3GIY+ojdhZhkO1gbG0118sIgphwSWKRxK0mvh6ERxKqIt1
xJEJO74EykXZV4oNJ8sjAjEA3J9r2ZghVhGN6V8DnQrTk24Td0E8hU8AcP0FVP+8
PQm/g/aXf2QQkQT+omdHVEJrAjEAy0pL0EBH6EVS98evDCBtQw22OZT52qXlAwZ2
gyTriKFVoqjeEjt3SZKKqXHSApP/AjBLpF99zcJJZRq2abgYlf9lv1chkrWqDHUu
DZttmYJeEfiFBBavVYIF1dOlZT0G8jMCMBc7sOSZodFnAiryP+Qg9otSBjJ3bQML
pSTqy7c3a2AScC/YyOwkDaICHnnD3XyjMwIxALRzl0tQEKMXs6hH8ToUdlLROCrP
EhQ0wahUTCk1gKA4uPD6TMTChavbh4K63OvbKg==
-----END RSA PRIVATE KEY-----"""
    privateKeys = {
        'ssh-rsa' : keys.Key.fromString(privateKey)
    }
    del privateKey

    def __init__(self, portal):
        self.portal = portal
