
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
# $Id: conch.py,v 1.16 2002/11/30 18:07:35 z3p Exp $

#""" Implementation module for the `ssh` command.
#"""

from twisted.conch.ssh import transport, userauth, connection, common, keys
from twisted.conch.ssh import session, forwarding
from twisted.internet import reactor, stdio, defer, protocol
from twisted.python import usage, log

import os, sys, getpass, struct, tty, fcntl, base64, signal

class GeneralOptions(usage.Options):
    synopsis = """Usage:    ssh [options] host [command]
 """

    optParameters = [['user', 'l', None, 'Log in using this user name.'],
                    ['identity', 'i', '~/.ssh/identity', 'Identity for public key authentication'],
                    ['escape', 'e', '~', "Set escape character; ``none'' = disable"],
                    ['cipher', 'c', None, 'Select encryption algorithm.'],
                    ['macs', 'm', None, 'Specify MAC algorithms for protocol version 2.'],
                    ['port', 'p', None, 'Connect to this port.  Server must be on the same port.'],
                    ['localforward', 'L', None, 'listen-port:host:port   Forward local port to remote address'],
                    ['remoteforward', 'R', None, 'listen-port:host:port   Forward remote port to local address'],
                    ]
    
    optFlags = [['null', 'n', 'Redirect input from /dev/null.'],
                ['tty', 't', 'Tty; allocate a tty even if command is given.'],
                ['notty', 'T', 'Do not allocate a tty.'],
                ['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['noshell', 'N', 'Do not execute a shell or command.'],
                ['subsystem', 's', 'Invoke command (mandatory) as SSH2 subsystem.'],
                ['log', 'v', 'Log to stderr']]

    identitys = ['~/.ssh/id_rsa', '~/.ssh/id_dsa']
    localForwards = []
    remoteForwards = []

    def opt_identity(self, i):
        self.identitys.append(i)

    def opt_escape(self, esc):
        if esc == 'none':
            self['escape'] = None
        elif esc[0] == '^':
            self['escape'] = chr(ord(esc[1])-64)
        else:
            self['escape'] = esc

    def opt_cipher(self, cipher):
        if cipher in SSHClientTransport.supportedCiphers:
            SSHClientTransport.supportedCiphers = [cipher]
        else:
            sys.exit("Unknown cipher type '%s'" % cipher)

    def opt_mac(self, mac):
        if mac in SSHClientTransport.supportedMACs:
            SSHClientTransport.supportedMACs = [mac]
        else:
            sys.exit("Unknown mac type '%s'" % mac)

    def opt_localforward(self, f):
        localPort, remoteHost, remotePort = f.split(':') # doesn't do v6 yet
        localPort = int(localPort)
        remotePort = int(remotePort)
        self.localForwards.append((localPort, (remoteHost, remotePort)))

    def opt_remoteforward(self, f):
        remotePort, connHost, connPort = f.split(':') # doesn't do v6 yet
        remotePort = int(remotePort)
        connPort = int(connPort)
        self.remoteForwards.append((remotePort, (connHost, connPort)))

    def opt_compress(self):
        SSHClientTransport.supportedCompressions[0:1] = ['zlib']

    def parseArgs(self, host, *command):
        self['host'] = host
        self['command'] = ' '.join(command)

# Rest of code in "run"
options = None
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
            tty.tcsetattr(fd, tty.TCSANOW, old)
    return exitStatus

class SSHClientFactory(protocol.ClientFactory):
    noisy = 1 

    def stopFactory(self):
        reactor.stop()

    def buildProtocol(self, addr):
        return SSHClientTransport()

class SSHClientTransport(transport.SSHClientTransport):

    def receiveDebug(self, alwaysDisplay, message, lang):
        global options
        if alwaysDisplay or options['log']:
            log.msg('Received Debug Message: %s' % message)

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
            split = line.split()
            if len(split) != 3: # old 4-field known_hosts entry (ssh1?)
                continue
            hosts, hostKeyType, encodedKey = split
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
        if not options['noshell']:
            self.openChannel(SSHSession())
        if options.localForwards:
            for localPort, hostport in options.localForwards:
                reactor.listenTCP(localPort,
                            forwarding.SSHLocalForwardingFactory(self, hostport))
        if options.remoteForwards:
            for remotePort, hostport in options.remoteForwards:
                log.msg('asking for remote forwarding for %s:%s' %
                        (remotePort, hostport))
                data = forwarding.packGlobal_tcpip_forward(
                    ('0.0.0.0', remotePort))
                d = self.sendGlobalRequest('tcpip-forward', data)
                self.remoteForwards[remotePort] = hostport

class SSHSession(session.SSHChannel):

    name = 'session'
    
    def channelOpen(self, foo):
        #global globalSession
        #globalSession = self
        # turn off local echo
        self.escapeMode = 1
        fd = 0 #sys.stdin.fileno()
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
        c = session.SSHSessionClient()
        if options['escape']:
            c.dataReceived = self.handleInput
        else:
            c.dataReceived = self.write
        c.connectionLost = self.sendEOF
        stdio.StandardIO(c)
        if options['subsystem']:
            self.conn.sendRequest(self, 'subsystem', \
                common.NS(options['command']))
        elif options['command']:
            if options['tty']:
                term = os.environ['TERM']
                winsz = fcntl.ioctl(fd, tty.TIOCGWINSZ, '12345678')
                winSize = struct.unpack('4H', winsz)
                ptyReqData = session.packRequest_pty_req(term, winSize, '')
                self.conn.sendRequest(self, 'pty-req', ptyReqData)                
            self.conn.sendRequest(self, 'exec', \
                common.NS(options['command']))
        else:
            if not options['notty']:
                term = os.environ['TERM']
                winsz = fcntl.ioctl(fd, tty.TIOCGWINSZ, '12345678')
                winSize = struct.unpack('4H', winsz)
                ptyReqData = session.packRequest_pty_req(term, winSize, '')
                self.conn.sendRequest(self, 'pty-req', ptyReqData)
            self.conn.sendRequest(self, 'shell', '')

    def handleInput(self, char):
        #log.msg('handling %s' % repr(char))
        if char in ('\n', '\r'):
            self.escapeMode = 1
            self.write(char)
        elif self.escapeMode == 1 and char == options['escape']:
            self.escapeMode = 2
        elif self.escapeMode == 2:
            self.escapeMode = 1 # so we can chain escapes together
            if char == '.': # disconnect
                log.msg('disconnecting from escape')
                reactor.stop()
                return
            elif char == '\x1a': # ^Z, suspend
                # following line courtesy of Erwin@freenode
                os.kill(os.getpid(), signal.SIGSTOP)
                return
            elif char == 'R': # rekey connection
                log.msg('rekeying connection')
                self.conn.transport.sendKexInit()
                return
            self.write('~' + char)
        else:
            self.escapeMode = 0
            self.write(char)

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
        exitStatus = int(struct.unpack('>L', data)[0])
        log.msg('exit status: %s' % exitStatus)

    def sendEOF(self):
        self.conn.sendEOF(self)

# Make it script-callable for testing purposes
if __name__ == "__main__":
    sys.exit(run())
