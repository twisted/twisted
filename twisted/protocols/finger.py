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
