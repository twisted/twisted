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
import os
import base64
try:
    import pwd
except:
    pwd = None
else:
    import crypt

from twisted.cred import identity
from twisted.internet import defer

import error

class ConchIdentity(identity.Identity):

    clients = {}    

    def validatePublicKey(self, pubKeyString):
        """
        this should return a Deferred, that gets either called or erred back,
        depending on if this is a valid key for the user
        """
        raise NotImplementedError

    def addServiceForSelf(self, serviceName):
        """this will add the service, using our name as the name for the
        perspective.
        """
        self.addKeyByString(serviceName, self.name)

    def addClientForService(self, serviceName, clientClass):
        """adds a client class for the given service
        """
        self.clients[serviceName] = clientClass

class OpenSSHConchIdentity(ConchIdentity):

    # XXX fail slower for security reasons
    def validatePublicKey(self, pubKeyString):
        home = os.path.expanduser('~%s/.ssh/' % self.name)
        if home[0] == '~': # couldn't expand
            return defer.fail(error.ConchError('not valid user'))
        for file in ['authorized_keys', 'authorized_keys2']:
            if os.path.exists(home+file):
                lines = open(home+file).readlines()
                for l in lines:
                    if base64.decodestring(l.split()[1])==pubKeyString:
                        return defer.succeed('')
        #print 'not valid key'
        return defer.fail(error.ConchError('not valid key'))

    def verifyPlainPassword(self, password):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(self.name)[1] # password
            except KeyError: # no such user
                return defer.fail(error.ConchError('no such user'))
            else:
                if cryptedPass in ['*', 'x']: # shadow, fail for now
                    return defer.fail(error.ConchError('cant read shadow'))
                ourCryptedPass = crypt.crypt(password, cryptedPass[:2])
                if ourCryptedPass == cryptedPass:
                    return defer.succeed('')
                return defer.fail(error.ConchError('bad password'))
        return defer.fail(error.ConchError('cannot do password auth')) # can't do password auth with out this now
