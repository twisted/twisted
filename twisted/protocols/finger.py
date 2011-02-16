# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""The Finger User Information Protocol (RFC 1288)"""

from twisted.protocols import basic
import string

class Finger(basic.LineReceiver):

    def lineReceived(self, line):
        parts = string.split(line)
        if not parts:
            parts = ['']
        if len(parts) == 1:
            slash_w = 0
        else:
            slash_w = 1
        user = parts[-1]
        if '@' in user:
            host_place = string.rfind(user, '@')
            user = user[:host_place]
            host = user[host_place+1:]
            return self.forwardQuery(slash_w, user, host)
        if user:
            return self.getUser(slash_w, user)
        else:
            return self.getDomain(slash_w)

    def _refuseMessage(self, message):
        self.transport.write(message+"\n")
        self.transport.loseConnection()

    def forwardQuery(self, slash_w, user, host):
        self._refuseMessage('Finger forwarding service denied')

    def getDomain(self, slash_w):
        self._refuseMessage('Finger online list denied')

    def getUser(self, slash_w, user):
        self.transport.write('Login: '+user+'\n')
        self._refuseMessage('No such user')
