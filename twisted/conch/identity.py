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
warnings.warn("twisted.conch.identity is deprecated", DeprecationWarning)

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
from twisted.cred.error import Unauthorized
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
        This should return a Deferred, that gets either called or erred back,
        depending on if this is a valid key for the user.

        @type pubKeyString: C{str}
        @rtype:             C{Deferred}
        """
        raise NotImplementedError

    def addServiceForSelf(self, serviceName):
        """
        This will add the service, using our name as the name for the
        perspective.  Currently unused.

        @type serviceName:  C{str}
        """
        self.addKeyByString(serviceName, self.name)

    def addClientForService(self, serviceName, clientClass):
        """
        Adds a client class for the given service.  Currently unused.

        @type serviceName:  C{str}
        @type clientClass:  C{class}
        """
        self.clients[serviceName] = clientClass

    def getUserGroupID(self):
        """
        Return a uid and gid for this user as a tuple (uid, gid).

        @rtype: C{tuple}
        """
        raise NotImplementedError

    def getHomeDir(self):
        """
        Return the users home directory.

        @rtype: C{str}
        """
        raise NotImplementedError

    def getShell(self):
        """
        Return the users shell.

        @rtype: C{str}
        """
        raise NotImplementedError

class OpenSSHConchIdentity(ConchIdentity):

    # XXX fail slower for security reasons
    def validatePublicKey(self, pubKeyString):
        home = os.path.expanduser('~%s/.ssh/' % self.name)
        if home[0] == '~': # couldn't expand
            return defer.fail(Unauthorized('not valid user'))
        uid, gid = os.geteuid(), os.getegid()
        ouid, ogid = pwd.getpwnam(self.name)[2:4]
        os.setegid(ogid)
        os.seteuid(ouid)
        for file in ['authorized_keys', 'authorized_keys2']:
            if os.path.exists(home+file):
                lines = open(home+file).readlines()
                for l in lines:
                    try:
                        l2 = l.split()
                        if len(l2) < 2:
                            continue
                        if base64.decodestring(l2[1])==pubKeyString:
                            os.setegid(gid)
                            os.seteuid(uid)
                            return defer.succeed('')
                    except binascii.Error:
                        pass # we caught an ssh1 key
        os.setegid(gid)
        os.seteuid(uid)
        return defer.fail(error.ConchError('not valid key'))

    def verifyPlainPassword(self, password):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(self.name)[1] # password
            except KeyError: # no such user
                return defer.fail(Unauthorized('no such user'))
            else:
                if cryptedPass not in ['*', 'x']:
                    if verifyCryptedPassword(cryptedPass, password):
                        return defer.succeed('')
                    return defer.fail(error.ConchError('bad password'))

        if shadow:
            gid = os.getegid()
            uid = os.geteuid()
            os.setegid(0)
            os.seteuid(0)
            try:
                shadowPass = shadow.getspnam(self.name)[1]
            except KeyError:
                os.setegid(gid)
                os.seteuid(uid)
                return defer.fail(Unauthorized('no such user'))
            os.setegid(gid)
            os.seteuid(uid)
            if verifyCryptedPassword(shadowPass, password):
                return defer.succeed('')
            return defer.fail(error.ConchError('bad password'))

        return defer.fail(error.ConchError('cannot do password auth')) # can't do password auth with out this now

    def getUserGroupID(self):
        if pwd:
            return pwd.getpwnam(self.name)[2:4]
        raise NotImplementedError

    def getHomeDir(self):
        if pwd:
            return pwd.getpwnam(self.name)[5]
        raise NotImplementedError

    def getShell(self):
        if pwd:
            return pwd.getpwnam(self.name)[6]
        raise NotImplementedError
