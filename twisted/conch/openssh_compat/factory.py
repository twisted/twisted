from twisted.conch.ssh import keys, factory, common
from twisted.python import log
import primes
import os

class OpenSSHFactory(factory.SSHFactory):
    dataRoot = '/usr/local/etc'
    moduliRoot = '/usr/local/etc' # for openbsd which puts moduli in a different
                                  # directory from keys
    def getPublicKeys(self):
        ks = {}
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-8:]=='_key.pub':
                try:
                    k = keys.getPublicKeyString(self.dataRoot+'/'+file)
                    t = common.getNS(k)[0]
                    ks[t] = k
                except Exception, e:
                    log.msg('bad public key file %s: %s' % (file,e))
        return ks
    def getPrivateKeys(self):
        ks = {}
        euid,egid = os.geteuid(), os.getegid()
        os.setegid(0) # gain priviledges
        os.seteuid(0)
        for file in os.listdir(self.dataRoot):
            if file[:9] == 'ssh_host_' and file[-4:]=='_key':
                try:
                    k = keys.getPrivateKeyObject(self.dataRoot+'/'+file)
                    t = keys.objectType(k)
                    ks[t] = k
                except Exception, e:
                    log.msg('bad private key file %s: %s' % (file, e))
        os.setegid(egid) # drop them just as quickily
        os.seteuid(euid)
        return ks

    def getPrimes(self):
        try:
            return primes.parseModuliFile(self.moduliRoot+'/moduli')
        except IOError:
            return None

