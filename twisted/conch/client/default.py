# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
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
from twisted.conch.error import ConchError
from twisted.conch.ssh import common, keys, userauth, agent
from twisted.internet import defer, protocol, reactor
from twisted.python import log

import agent

import os, sys, base64, getpass

def verifyHostKey(transport, host, pubKey, fingerprint):
    goodKey = isInKnownHosts(host, pubKey)
    if goodKey == 1: # good key
        return defer.succeed(1)
    elif goodKey == 2: # AAHHHHH changed
        return defer.fail(ConchError('changed host key'))
    else:
        oldout, oldin = sys.stdout, sys.stdin
        sys.stdin = sys.stdout = open('/dev/tty','r+')
        if host == transport.transport.getPeer().host:
            khHost = host
        else:
            host = '%s (%s)' % (host,
                                transport.transport.getPeer().host)
            khHost = '%s,%s' % (host,
                                transport.transport.getPeer().host)
        keyType = common.getNS(pubKey)[0]
        print """The authenticity of host '%s' can't be extablished.
%s key fingerprint is %s.""" % (host,
                            {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType],
                            fingerprint)
        try:
            ans = raw_input('Are you sure you want to continue connecting (yes/no)? ')
        except KeyboardInterrupt:
            return defer.fail(ConchError("^C"))
        while ans.lower() not in ('yes', 'no'):
            ans = raw_input("Please type 'yes' or 'no': ")
        sys.stdout,sys.stdin=oldout,oldin
        if ans == 'no':
            print 'Host key verification failed.'
            return defer.fail(ConchError('bad host key'))
        print "Warning: Permanently added '%s' (%s) to the list of known hosts." % (khHost, {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType])
        known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'), 'a')
        encodedKey = base64.encodestring(pubKey).replace('\n', '')
        known_hosts.write('\n%s %s %s' % (khHost, keyType, encodedKey))
        known_hosts.close()
        return defer.succeed(1)

def isInKnownHosts(host, pubKey):
    """checks to see if host is in the known_hosts file for the user.
    returns 0 if it isn't, 1 if it is and is the same, 2 if it's changed.
    """
    keyType = common.getNS(pubKey)[0]
    retVal = 0
    if not os.path.exists(os.path.expanduser('~/.ssh/')):
        print 'Creating ~/.ssh directory...'
        os.mkdir(os.path.expanduser('~/.ssh'))
    try:
        known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'))
    except IOError:
        return 0
    for line in known_hosts.xreadlines():
        split = line.split()
        if len(split) != 3: # old 4-field known_hosts entry (ssh1?)
            continue
        hosts, hostKeyType, encodedKey = split
        if host not in hosts.split(','): # incorrect host
            continue
        if hostKeyType != keyType: # incorrect type of key
            continue
        try:
            decodedKey = base64.decodestring(encodedKey)
        except:
            continue
        if decodedKey == pubKey:
            return 1
        else:
            retVal = 2
    return retVal

class SSHUserAuthClient(userauth.SSHUserAuthClient):
    usedFiles = []

    def __init__(self, user, options, *args):
        userauth.SSHUserAuthClient.__init__(self, user, *args)
        self.keyAgent = None
        self.options = options

    def serviceStarted(self):
        if 'SSH_AUTH_SOCK' in os.environ:
            log.msg('using agent')
            cc = protocol.ClientCreator(reactor, agent.SSHAgentClient)
            d = cc.connectUNIX(os.environ['SSH_AUTH_SOCK'])
            d.addCallback(self._setAgent)
            d.addErrback(self._ebSetAgent)
        else:
            userauth.SSHUserAuthClient.serviceStarted(self)

    def _setAgent(self, a):
        self.keyAgent = a
        d = self.keyAgent.getPublicKeys()
        d.addBoth(self._ebSetAgent)
        return d

    def _ebSetAgent(self, f):
        userauth.SSHUserAuthClient.serviceStarted(self)

    def getPassword(self, prompt = None):
        if not prompt:
            prompt = "%s@%s's password: " % (self.user, self.transport.transport.getPeer().host)
        try:
            oldout, oldin = sys.stdout, sys.stdin
            sys.stdin = sys.stdout = open('/dev/tty','r+')
            p=getpass.getpass(prompt)
            sys.stdout,sys.stdin=oldout,oldin
            return defer.succeed(p)
        except KeyboardInterrupt, e:
            print
            return defer.fail(ConchError('PEBKAC'))

    def getPublicKey(self):
        if self.keyAgent:
            blob = self.keyAgent.getPublicKey()
            if blob:
                return blob
        files = [x for x in self.options.identitys if x not in self.usedFiles]
        log.msg(str(self.options.identitys))
        log.msg(str(files))
        if not files:
            return None
        file = files[0]
        log.msg(file)
        self.usedFiles.append(file)
        file = os.path.expanduser(file)
        file += '.pub'
        if not os.path.exists(file):
            return self.getPublicKey() # try again
        try:
            return keys.getPublicKeyString(file)
        except:
            return self.getPublicKey() # try again

    def signData(self, publicKey, signData):
        if not self.usedFiles: # agent key
            return self.keyAgent.signData(publicKey, signData)
        else:
            return userauth.SSHUserAuthClient.signData(self, publicKey, signData)

    def getPrivateKey(self):
        file = os.path.expanduser(self.usedFiles[-1])
        if not os.path.exists(file):
            return None
        try:
            return defer.succeed(keys.getPrivateKeyObject(file))
        except keys.BadKeyError, e:
            if e.args[0] == 'encrypted key with no passphrase':
                for i in range(3):
                    prompt = "Enter passphrase for key '%s': " % \
                           self.usedFiles[-1]
                    oldout, oldin = sys.stdout, sys.stdin
                    sys.stdin = sys.stdout = open('/dev/tty','r+')
                    p=getpass.getpass(prompt)
                    sys.stdout,sys.stdin=oldout,oldin
                    try:
                        return defer.succeed(keys.getPrivateKeyObject(file, passphrase = p))
                    except keys.BadKeyError:
                        pass
                return defer.fail(ConchError('bad password'))
            raise
        except KeyboardInterrupt:
            print
            reactor.stop()

