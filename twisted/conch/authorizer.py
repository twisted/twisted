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

"""This module is deprecated."""

import warnings
warnings.warn("twisted.conch.authorizer is deprecated", DeprecationWarning)

from twisted.cred import authorizer
from twisted.cred.error import Unauthorized
from twisted.internet import defer
from twisted.python import log
import identity

class OpenSSHConchAuthorizer(authorizer.DefaultAuthorizer):
    identityClass = identity.OpenSSHConchIdentity

    def getIdentityRequest(self, name):
        """
        Return a Deferred that will callback with an Identity for the given
        name.  For the purposes of Conch, this should B{always} callback with
        an Identity to prevent attackers from learning what users are valid
        and which aren't.

        @type name: C{str}
        @rtype:     C{Deferred}
        """
        if not self.identities.has_key(name):
            log.msg('adding %s for %s' % (self.identityClass, name))
            self.addIdentity(self.identityClass(name, self))
        return defer.succeed(self.identities[name])


