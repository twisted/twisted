# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 
import pwd
from twisted.cred import authorizer
from twisted.internet import defer
from twisted.python import log
import identity, error

class OpenSSHConchAuthorizer(authorizer.DefaultAuthorizer):
    identityClass = identity.OpenSSHConchIdentity

    def getIdentityRequest(self, name):
        try:
            pwd.getpwnam(name)
        except KeyError:
            defer.fail(error.ConchError('not a valid key'))
        else:
            if not self.identities.has_key(name):
                log.msg('adding %s for %s' % (self.identityClass, name))
                self.addIdentity(self.identityClass(name, self))
            return defer.succeed(self.identities[name])
