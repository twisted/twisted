
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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
# $Id: conch.py,v 1.10 2002/11/10 07:36:51 spiv Exp $

#""" Implementation module for the `ssh` command.
#"""

from twisted.conch.ssh import transport, userauth, connection, common, keys
from twisted.internet import reactor, stdio, defer, protocol
from twisted.python import usage, log

import os, sys, getpass, struct, tty, fcntl, base64

class GeneralOptions(usage.Options):
    synopsis = """Usage:    ssh [options] host [command]
 """

    optParameters = [['user', 'l', None, 'Log in using this user name.'],
                  ['identity', 'i', '~/.ssh/identity', 'Identity for public key authentication'],
                  ['cipher', 'c', None, 'Select encryption algorithm.'],
                  ['macs', 'm', None, 'Specify MAC algorithms for protocol version 2.'],
                  ['port', 'p', None, 'Connect to this port.  Server must be on the same port.']]
                  
    
    optFlags = [['null', 'n', 'Redirect input from /dev/null.'],
                ['tty', 't', 'Tty; allocate a tty even if command is given.'],
                ['notty', 'T', 'Do not allocate a tty.'],
                ['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['noshell', 'N', 'Do not execute a shell or command.'],
                ['subsystem', 's', 'Invoke command (mandatory) as SSH2 subsystem.'],
                ['log', '', 'Log to stderr']]

    identitys = ['~/.ssh/id_rsa', '~/.ssh/id_dsa']

    def opt_identity(self, i):
        self.identitys.append(i)

    def parseArgs(self, host, *command):
        self['host'] = host
        self['command'] = ' '.join(command)

# Rest of code in "run"
options = {}
exitStatus = 0

def run():
    global options
    args = sys.argv[1:]
    if '-l' in args: # cvs is an idiot
        i = args.index('-l')
        args = args[i:i+2]+args
        del args[i+2:i+4]
    options = GeneralOptions()
    try:
        options.parseOptions(args)
    except usage.UsageError, u:
        print 'ERROR: %s' % u
        options.opt_help()
        sys.exit(1)
    if options['log']:
        realout = sys.stdout
        log.startLogging(sys.stderr)
        sys.stdout = realout
    else:
        log.discardLogs()
    if '@' in options['host']:
        options['user'], options['host'] = options['host'].split('@',1)
    host = options['host']
    port = int(options['port'] or 22)
    log.msg(str((host,port)))
    reactor.connectTCP(host, port, SSHClientFactory())
    fd = sys.stdin.fileno()
    try:
        old = tty.tcgetattr(fd)
    except:
        old = None
    try:
        reactor.run()
    finally:
        if old:
            tty.tcsetattr(fd, tty.TCSADRAIN, old)
    return exitStatus

class SSHClientFactory(protocol.ClientFactory):
    noisy = 1 

    def stopFactory(self):
        reactor.stop()

    def buildProtocol(self, addr):
        return SSHClientTransport()

class SSHClientTransport(transport.SSHClientTransport):
    def verifyHostKey(self, pubKey, fingerprint):
        goodKey = self.isInKnownHosts(options['host'], pubKey)
        if goodKey == 1: # good key
            return 1
        elif goodKey == 2: # AAHHHHH changed
            return 0
        else:
            oldout, oldin = sys.stdout, sys.stdin
            sys.stdin = sys.stdout = open('/dev/tty','r+')
            if options['host'] == self.transport.getPeer()[1]:
                host = options['host']
                khHost = options['host']
            else:
                host = '%s (%s)' % (options['host'], 
                                    self.transport.getPeer()[1])
                khHost = '%s,%s' % (options['host'], 
                                    self.transport.getPeer()[1])
            keyType = common.getNS(pubKey)[0]
            print """The authenticity of host '%s' can't be extablished.
%s key fingerprint is %s.""" % (host, 
                                {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType], 
                                fingerprint) 
            ans = raw_input('Are you sure you want to continue connecting (yes/no)? ')
            while ans.lower() not in ('yes', 'no'):
                ans = raw_input("Please type 'yes' or 'no': ")
            sys.stdout,sys.stdin=oldout,oldin
            if ans == 'no':
                print 'Host key verification failed.'
                return 0
            print "Warning: Permanently added '%s' (%s) to the list of known hosts." % (khHost, {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType])
            known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'), 'a')
            encodedKey = base64.encodestring(pubKey).replace('\n', '')
            known_hosts.write('%s %s %s' % (khHost, keyType, encodedKey))
            known_hosts.close()
            return 1

    def isInKnownHosts(self, host, pubKey):
        """checks to see if host is in the known_hosts file for the user.
        returns 0 if it isn't, 1 if it is and is the same, 2 if it's changed.
        """
        keyType = common.getNS(pubKey)[0]
        retVal = 0
        try:
            known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'))
        except IOError:
            return 0
        for line in known_hosts.xreadlines():
            try:
                hosts, hostKeyType, encodedKey = line.split()
            except ValueError: # old 4-field known_hosts entry (ssh1?)
                continue
            if not host in hosts.split(','): # incorrect host
                continue
            if not hostKeyType == keyType: # incorrect type of key
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

    def connectionSecure(self):
        if options['user']:
            user = options['user']
        else:
            user = getpass.getuser()
        self.requestService(SSHUserAuthClient(user, SSHConnection()))

class SSHUserAuthClient(userauth.SSHUserAuthClient):
    usedFiles = []

    def getPassword(self, prompt = None):
#        self.passDeferred = defer.Deferred()
        if not prompt:
            prompt = "%s@%s's password: " % (self.user, options['host'])
        #return self.passDeferred
        oldout, oldin = sys.stdout, sys.stdin
        sys.stdin = sys.stdout = open('/dev/tty','r+')
        p=getpass.getpass(prompt)
        sys.stdout,sys.stdin=oldout,oldin
        return defer.succeed(p)
        

    def gotPassword(self, q, password):
        d = self.passDeferred
        del self.passDeferred
        d.callback(password)

    def getPublicKey(self):
        files = [x for x in options.identitys if x not in self.usedFiles]
        if not files:
            return None
        file = files[0]
        log.msg(file)
        self.usedFiles.append(file)
        file = os.path.expanduser(file) 
        file += '.pub'
        if not os.path.exists(file):
            return
        return keys.getPublicKeyString(file) 
    
    def getPrivateKey(self):
# doesn't handle encryption
        file = os.path.expanduser(self.usedFiles[-1])
        if not os.path.exists(file):
            return None
        return keys.getPrivateKeyObject(file)

class SSHConnection(connection.SSHConnection):
    def serviceStarted(self):
# port forwarding will go here
        if not options['notty']:
            self.openChannel(SSHSession())

class SSHSession(connection.SSHChannel):
    name = 'session'
    
    def channelOpen(self, foo):
        global session
        session = self
        # turn off local echo
        fd = sys.stdin.fileno()
        try:
            new = tty.tcgetattr(fd)
        except:
            log.msg('not a typewriter!') 
        else:
            new[3] = new[3] & ~tty.ICANON & ~tty.ECHO
            new[6][tty.VMIN] = 1
            new[6][tty.VTIME] = 0
            tty.tcsetattr(fd, tty.TCSANOW, new)
            tty.setraw(fd)
        c = connection.SSHSessionClient()
        c.dataReceived = self.write
        c.connectionLost = self.sendEOF
        stdio.StandardIO(c)
        term = os.environ['TERM']
        if options['subsystem']:
            self.conn.sendRequest(self, 'subsystem', \
                common.NS(options['command']))
        elif options['command']:
            self.conn.sendRequest(self, 'exec', \
                common.NS(options['command']))
        else:
            winsz = fcntl.ioctl(fd, tty.TIOCGWINSZ, '12345678')
            rows, columns, xpixels, ypixels = struct.unpack('4H', winsz)
            self.conn.sendRequest(self, 'pty-req', common.NS(term) + \
                struct.pack('>4L', columns, rows, xpixels, ypixels) + \
                common.NS(''))
            self.conn.sendRequest(self, 'shell', '')

    def dataReceived(self, data):
        sys.stdout.write(data)
        sys.stdout.flush()
        #sys.stdout.flush()

    def extReceived(self, t, data):
        if t==connection.EXTENDED_DATA_STDERR:
            log.msg('got %s stderr data' % len(data))
            sys.stderr.write(data)
            sys.stderr.flush()

    def eofReceived(self):
        log.msg('got eof')
        sys.stdin.close()

    def closed(self):
        log.msg('closed %s' % self)
        if len(self.conn.channels) == 1: # just us left
            reactor.stop()

    def request_exit_status(self, data):
        global exitStatus
        exitStatus = struct.unpack('>L', data)[0]
        log.msg('exit status: %s' % exitStatus)

    def sendEOF(self):
        self.conn.sendEOF(self)

# Make it script-callable for testing purposes
if __name__ == "__main__":
    sys.exit(run())
