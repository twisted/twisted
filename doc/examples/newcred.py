# -*- coding: Latin-1 -*-

import sys

from twisted.protocols import basic
from twisted.internet import protocol
from twisted.python import components
from twisted.python import log

from twisted.cred import error
from twisted.cred import portal
from twisted.cred import checkers
from twisted.cred import credentials

class IProtocolUser(components.Interface):
    def getPrivileges(self):
        """Return a list of privileges this user has."""

    def logout(self):
        """Cleanup per-login resources allocated to this avatar"""

class AnonymousUser:
    __implements__ = (IProtocolUser,)
    
    def getPrivileges(self):
        return [1, 2, 3]

    def logout(self):
        pass

class RegularUser:
    __implements__ = (IProtocolUser,)
    
    def getPrivileges(self):
        return [1, 2, 3, 5, 6]

    def logout(self):
        print "Cleaning up regular user resources"

class Administrator:
    __implements__ = (IProtocolUser,)
    
    def getPrivileges(self):
        return range(50)

    def logout(self):
        print "Cleaning up administrator resources"

class Protocol(basic.LineReceiver):
    user = None
    avatar = AnonymousUser()
    portal = None
    logout = None

    def connectionMade(self):
        self.sendLine("Login with USER <name> followed by PASS <password>")
        self.sendLine("Check privileges with PRIVS")
    
    def lineReceived(self, line):
        f = getattr(self, 'cmd_' + line.upper().split()[0])
        if f:
            try:
                f(*line.split()[1:])
            except TypeError:
                self.sendLine("Wrong number of arguments.")
            except:
                self.sendLine("Server error (probably your fault)")
    
    def cmd_USER(self, name):
        self.user = name
        self.sendLine("Alright.  Now PASS?")
    
    def cmd_PASS(self, password):
        if not self.user:
            self.sendLine("USER required before PASS")
        else:
            if self.portal:
                print self.user, password
                self.portal.login(
                    credentials.UsernamePassword(self.user, password),
                    None,
                    IProtocolUser
                ).addCallbacks(self._cbLogin, self._ebLogin
                )
            else:
                self.sendLine("DENIED")

    def cmd_PRIVS(self):
        self.sendLine("You have the following privileges: ")
        self.sendLine(" ".join(map(str, self.avatar.getPrivileges())))

    def _cbLogin(self, (interface, avatar, logout)):
        assert interface is IProtocolUser
        self.avatar = avatar
        self.logout = logout
        self.sendLine("Login successful.  Available commands: PRIVS")
    
    def _ebLogin(self, failure):
        failure.trap(error.UnauthorizedLogin)
        self.sendLine("Login denied!  Go away.")

class ServerFactory(protocol.ServerFactory):
    protocol = Protocol
    
    def __init__(self, portal):
        self.portal = portal
    
    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.portal = self.portal
        return p

class Realm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if IProtocolUser in interfaces:
            if avatarId.isupper():
                # Capitalized usernames are administrators.
                av = Administrator()
            else:
                av = RegularUser()
            return IProtocolUser, av, av.logout
        raise NotImplementedError("Only IProtocolUser interface is supported by this realm")

def main():
    r = Realm()
    p = portal.Portal(r)
    c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
    c.addUser("auser", "thepass")
    c.addUser("SECONDUSER", "secret")
    p.registerChecker(c)
    
    f = ServerFactory(p)

    log.startLogging(sys.stdout)

    from twisted.internet import reactor
    reactor.listenTCP(4738, f)
    reactor.run()

if __name__ == '__main__':
    main()
