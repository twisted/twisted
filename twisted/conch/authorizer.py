# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

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


