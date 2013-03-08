# -*- test-case-name: twisted.conch.test.test_knownhosts,twisted.conch.test.test_default -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Various classes and functions for implementing user-interaction in the
command-line conch client.

You probably shouldn't use anything in this module directly, since it assumes
you are sitting at an interactive terminal.  For example, to programmatically
interact with a known_hosts database, use L{twisted.conch.client.knownhosts}.
"""

from twisted.python import log
from twisted.python.filepath import FilePath

from twisted.conch.error import ConchError
from twisted.conch.ssh import common, keys, userauth
from twisted.internet import defer, protocol, reactor

from twisted.conch.client.knownhosts import KnownHostsFile, ConsoleUI

from twisted.conch.client import agent

import os, sys, base64, getpass

# This name is bound so that the unit tests can use 'patch' to override it.
_open = open

def verifyHostKey(transport, host, pubKey, fingerprint):
    """
    Verify a host's key.

    This function is a gross vestige of some bad factoring in the client
    internals.  The actual implementation, and a better signature of this logic
    is in L{KnownHostsFile.verifyHostKey}.  This function is not deprecated yet
    because the callers have not yet been rehabilitated, but they should
    eventually be changed to call that method instead.

    However, this function does perform two functions not implemented by
    L{KnownHostsFile.verifyHostKey}.  It determines the path to the user's
    known_hosts file based on the options (which should really be the options
    object's job), and it provides an opener to L{ConsoleUI} which opens
    '/dev/tty' so that the user will be prompted on the tty of the process even
    if the input and output of the process has been redirected.  This latter
    part is, somewhat obviously, not portable, but I don't know of a portable
    equivalent that could be used.

    @param host: Due to a bug in L{SSHClientTransport.verifyHostKey}, this is
    always the dotted-quad IP address of the host being connected to.
    @type host: L{str}

    @param transport: the client transport which is attempting to connect to
    the given host.
    @type transport: L{SSHClientTransport}

    @param fingerprint: the fingerprint of the given public key, in
    xx:xx:xx:... format.  This is ignored in favor of getting the fingerprint
    from the key itself.
    @type fingerprint: L{str}

    @param pubKey: The public key of the server being connected to.
    @type pubKey: L{str}

    @return: a L{Deferred} which fires with C{1} if the key was successfully
    verified, or fails if the key could not be successfully verified.  Failure
    types may include L{HostKeyChanged}, L{UserRejectedKey}, L{IOError} or
    L{KeyboardInterrupt}.
    """
    actualHost = transport.factory.options['host']
    actualKey = keys.Key.fromString(pubKey)
    kh = KnownHostsFile.fromPath(FilePath(
            transport.factory.options['known-hosts']
            or os.path.expanduser("~/.ssh/known_hosts")
            ))
    ui = ConsoleUI(lambda : _open("/dev/tty", "r+b"))
    return kh.verifyHostKey(ui, actualHost, host, actualKey)



def isInKnownHosts(host, pubKey, options):
    """checks to see if host is in the known_hosts file for the user.
    returns 0 if it isn't, 1 if it is and is the same, 2 if it's changed.
    """
    keyType = common.getNS(pubKey)[0]
    retVal = 0

    if not options['known-hosts'] and not os.path.exists(os.path.expanduser('~/.ssh/')):
        print 'Creating ~/.ssh directory...'
        os.mkdir(os.path.expanduser('~/.ssh'))
    kh_file = options['known-hosts'] or '~/.ssh/known_hosts'
    try:
        known_hosts = open(os.path.expanduser(kh_file))
    except IOError:
        return 0
    for line in known_hosts.xreadlines():
        split = line.split()
        if len(split) < 3:
            continue
        hosts, hostKeyType, encodedKey = split[:3]
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

    def __init__(self, user, options, *args):
        userauth.SSHUserAuthClient.__init__(self, user, *args)
        self.keyAgent = None
        self.options = options
        self.usedFiles = []
        if not options.identitys:
            options.identitys = ['~/.ssh/id_rsa', '~/.ssh/id_dsa']

    def serviceStarted(self):
        if 'SSH_AUTH_SOCK' in os.environ and not self.options['noagent']:
            log.msg('using agent')
            cc = protocol.ClientCreator(reactor, agent.SSHAgentClient)
            d = cc.connectUNIX(os.environ['SSH_AUTH_SOCK'])
            d.addCallback(self._setAgent)
            d.addErrback(self._ebSetAgent)
        else:
            userauth.SSHUserAuthClient.serviceStarted(self)

    def serviceStopped(self):
        if self.keyAgent:
            self.keyAgent.transport.loseConnection()
            self.keyAgent = None

    def _setAgent(self, a):
        self.keyAgent = a
        d = self.keyAgent.getPublicKeys()
        d.addBoth(self._ebSetAgent)
        return d

    def _ebSetAgent(self, f):
        userauth.SSHUserAuthClient.serviceStarted(self)

    def _getPassword(self, prompt):
        try:
            oldout, oldin = sys.stdout, sys.stdin
            sys.stdin = sys.stdout = open('/dev/tty','r+')
            p=getpass.getpass(prompt)
            sys.stdout,sys.stdin=oldout,oldin
            return p
        except (KeyboardInterrupt, IOError):
            print
            raise ConchError('PEBKAC')

    def getPassword(self, prompt = None):
        if not prompt:
            prompt = "%s@%s's password: " % (self.user, self.transport.transport.getPeer().host)
        try:
            p = self._getPassword(prompt)
            return defer.succeed(p)
        except ConchError:
            return defer.fail()


    def getPublicKey(self):
        """
        Get a public key from the key agent if possible, otherwise look in
        the next configured identity file for one.
        """
        if self.keyAgent:
            key = self.keyAgent.getPublicKey()
            if key is not None:
                return key
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
            return keys.Key.fromFile(file)
        except keys.BadKeyError:
            return self.getPublicKey() # try again


    def signData(self, publicKey, signData):
        """
        Extend the base signing behavior by using an SSH agent to sign the
        data, if one is available.

        @type publicKey: L{Key}
        @type signData: C{str}
        """
        if not self.usedFiles: # agent key
            return self.keyAgent.signData(publicKey.blob(), signData)
        else:
            return userauth.SSHUserAuthClient.signData(self, publicKey, signData)


    def getPrivateKey(self):
        """
        Try to load the private key from the last used file identified by
        C{getPublicKey}, potentially asking for the passphrase if the key is
        encrypted.
        """
        file = os.path.expanduser(self.usedFiles[-1])
        if not os.path.exists(file):
            return None
        try:
            return defer.succeed(keys.Key.fromFile(file))
        except keys.EncryptedKeyError:
            for i in range(3):
                prompt = "Enter passphrase for key '%s': " % \
                    self.usedFiles[-1]
                try:
                    p = self._getPassword(prompt)
                    return defer.succeed(keys.Key.fromFile(file, passphrase=p))
                except (keys.BadKeyError, ConchError):
                    pass
                return defer.fail(ConchError('bad password'))
            raise
        except KeyboardInterrupt:
            print
            reactor.stop()


    def getGenericAnswers(self, name, instruction, prompts):
        responses = []
        try:
            oldout, oldin = sys.stdout, sys.stdin
            sys.stdin = sys.stdout = open('/dev/tty','r+')
            if name:
                print name
            if instruction:
                print instruction
            for prompt, echo in prompts:
                if echo:
                    responses.append(raw_input(prompt))
                else:
                    responses.append(getpass.getpass(prompt))
        finally:
            sys.stdout,sys.stdin=oldout,oldin
        return defer.succeed(responses)
