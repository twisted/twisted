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
            return defer.fail('')
        for file in ['authorized_keys', 'authorized_keys2']:
            if os.path.exists(home+file):
                lines = open(home+file).readlines()
                for l in lines:
                    if base64.decodestring(l.split()[1])==pubKey:
                        return defer.succeed('')
        print 'not vaild key'
        return defer.fail('')

    def verifyPlainPassword(self, password):
        if pwd:
            try:
                cryptedPass = pwd.getpwnam(self.name)[1] # password
            except KeyError: # no such user
                return defer.fail('')
            else:
                if cryptedPass in ['*', 'x']: # shadow, fail for now
                    return defer.fail('')
                ourCryptedPass = crypt.crypt(password, cryptedPass[:2])
                if ourCryptedPass == cryptedPass:
                    return defer.succeed('')
                return defer.fail('')
        return defer.fail('') # can't do password auth with out this now