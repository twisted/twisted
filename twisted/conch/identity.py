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

"""Identity for Conch.  This adds the method validatePublicKey which checks to see if a public key is a valid identifier for a user.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import os
import base64
import binascii
try:
    import pwd
except:
    pwd = None
else:
    import crypt

try:
    # get these from http://www.twistedmatrix.com/users/z3p/files/pyshadow-0.1.tar.gz
    import md5_crypt
    import shadow
except:
    shadow = None
    md5_crypt = None

from twisted.cred import identity
from twisted.internet import defer

import error

def verifyCryptedPassword(crypted, pw):
    if crypted[0] == '$': # md5_crypted
        if not md5_crypt: return 0
        salt = crypted.split('$')[2]
        return md5_crypt.md5_crypt(pw, salt) == crypted
    if not pwd:
        return 0
    return crypt.crypt(pw, crypted[:2]) == crypted 

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

    def getUserGroupID(self):
        """return a tuple of (uid, gid) for this user.
        """
        raise NotImplementedError

    def getHomeDir(self):
        """return the home directory for this user.
        """
        raise NotImplementedError

    def getShell(self):
        """return the shell for this user.
        """
        raise NotImplementedError

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
                    try:
                        if base64.decodestring(l.split()[1])==pubKeyString:
                            return defer.succeed('')
                    except binascii.Error:
                        pass # we caught an ssh1 key
        return defer.fail(error.ConchError('not valid key'))

    def verifyPlainPassword(self, password):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(self.name)[1] # password
            except KeyError: # no such user
                return defer.fail(error.ConchError('no such user'))
            else:
                if cryptedPass not in ['*', 'x']:
                    if verifyCryptedPassword(cryptedPass, password):
                        return defer.succeed('')
                    return defer.fail(error.ConchError('bad password'))

        if shadow:
            try:
                shadowPass = shadow.getspnam(self.name)[1]
            except KeyError:
                return defer.fail(error.ConchError('no such user'))
            if verifyCryptedPassword(shadowPass, password):
                return defer.succeed('')
            return defer.fail(error.ConchError('bad password'))

        return defer.fail(error.ConchError('cannot do password auth')) # can't do password auth with out this now

    def getUserGroupID(self):
        if pwd:
           return pwd.getpwnam(self.name)[2:4]

        raise NotImplementedError, 'cannot get uid/gid without pwd'

    def getHomeDir(self):
        if pwd:
            return pwd.getpwnam(self.name)[5]

        raise NotImplementedError, 'cannot get home directory without pwd'

    def getShell(self):
        if pwd:
            return pwd.getpwnam(self.name)[6]

        raise NotImplementedError, 'cannot get shell without pwd'
