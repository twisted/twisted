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
# $Id: tkconch.py,v 1.1 2002/12/27 23:56:00 z3p Exp $

""" Implementation module for the `tkconch` command.
"""

from __future__ import nested_scopes

import Tkinter, tkFont, string
from twisted.conch import tkvt100
from twisted.conch.ssh import transport, userauth, connection, common, keys
from twisted.conch.ssh import session, forwarding
from twisted.internet import reactor, defer, protocol, tksupport
from twisted.python import usage, log

import os, sys, getpass, struct, base64, signal

colorKeys = (
    'b', 'r', 'g', 'y', 'l', 'm', 'c', 'w',
    'B', 'R', 'G', 'Y', 'L', 'M', 'C', 'W'
)

colorMap = {
    'b': '#000000', 'r': '#c40000', 'g': '#00c400', 'y': '#c4c400',
    'l': '#000080', 'm': '#c400c4', 'c': '#00c4c4', 'w': '#c4c4c4',
    'B': '#626262', 'R': '#ff0000', 'G': '#00ff00', 'Y': '#ffff00',
    'L': '#0000ff', 'M': '#ff00ff', 'C': '#00ffff', 'W': '#ffffff',
}

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
                    ['option', 'o', None, 'Ignored OpenSSH options'],
                    ]
    
    optFlags = [['null', 'n', 'Redirect input from /dev/null.'],
                ['tty', 't', 'Tty; allocate a tty even if command is given.'],
                ['notty', 'T', 'Do not allocate a tty.'],
                ['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['noshell', 'N', 'Do not execute a shell or command.'],
                ['subsystem', 's', 'Invoke command (mandatory) as SSH2 subsystem.'],
                ['log', 'v', 'Log to stderr'],
                ['nox11', 'x']]

    identitys = []
    localForwards = []
    remoteForwards = []

    def opt_identity(self, i):
        self.identitys.append(i)

    def opt_escape(self, esc):
        if esc == 'none':
            self['escape'] = None
        elif esc[0] == '^' and len(esc) == 2:
            self['escape'] = chr(ord(esc[1])-64)
        elif len(esc) == 1:
            self['escape'] = esc
        else:
            sys.exit("Bad escape character '%s'." % esc)

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
frame = None

def deferredAskFrame(question, echo):
    if frame.callback:
        raise "can't ask 2 questions at once!"
    d = defer.Deferred()
    resp = []
    def gotChar(ch, resp=resp):
        if not ch: return
        if ch=='\x03': # C-c
            reactor.stop()
        if ch=='\r':
            frame.write('\r\n')
            stresp = ''.join(resp)
            del resp
            frame.callback = None
            d.callback(stresp)
            return
        elif 32 <= ord(ch) < 127:
            resp.append(ch)
            if echo:
                frame.write(ch)
        elif ord(ch) == 8 and resp: # BS
            frame.write('\x08 \x08')
            resp.pop()
    frame.callback = gotChar
    frame.write(question)
    frame.canvas.focus_force()
    return d

def run():
    global options, frame
    args = sys.argv[1:]
    if '-l' in args: # cvs is an idiot
        i = args.index('-l')
        args = args[i:i+2]+args
        del args[i+2:i+4]
    for arg in args[:]:
        try:
            i = args.index(arg)
            if arg[:2] == '-o' and args[i+1][0]!='-':
                args[i:i+2] = [] # suck on it scp
        except ValueError:
            pass
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
    log.deferr = handleError # HACK
    if '@' in options['host']:
        options['user'], options['host'] = options['host'].split('@',1)
    if not options.identitys:
        options.identitys = ['~/.ssh/id_rsa', '~/.ssh/id_dsa']
    host = options['host']
    port = int(options['port'] or 22)
    log.msg((host,port))
    reactor.connectTCP(host, port, SSHClientFactory())
    root = Tkinter.Tk()
    frame = tkvt100.VT100Frame(root, callback=None)
    root.geometry('%dx%d'%(tkvt100.fontWidth*frame.width+3, tkvt100.fontHeight*frame.height+3))
    frame.pack(side = Tkinter.TOP)
    tksupport.install(root)
    reactor.run()
    sys.exit(exitStatus)

def handleError():
    from twisted.python import failure
    global exitStatus
    exitStatus = 2
    log.err(failure.Failure())
    reactor.stop()
    raise

class SSHClientFactory(protocol.ClientFactory):
    noisy = 1 

    def stopFactory(self):
        reactor.stop()

    def buildProtocol(self, addr):
        return SSHClientTransport()

class SSHClientTransport(transport.SSHClientTransport):

    def receiveError(self, code, desc):
        global exitStatus
        exitStatus = 'conch:\tRemote side disconnected with error code %i\nconch:\treason: %s' % (code, desc)

    def sendDisconnect(self, code, reason):
        global exitStatus
        exitStatus = 'conch:\tSending disconnect with error code %i\nconch:\treason: %s' % (code, reason)
        transport.SSHClientTransport.sendDisconnect(self, code, reason)

    def receiveDebug(self, alwaysDisplay, message, lang):
        global options
        if alwaysDisplay or options['log']:
            log.msg('Received Debug Message: %s' % message)

    def verifyHostKey(self, pubKey, fingerprint):
        #d = defer.Deferred()
        #d.addCallback(lambda x:defer.succeed(1))
        #d.callback(2)
        #return d
        goodKey = self.isInKnownHosts(options['host'], pubKey)
        if goodKey == 1: # good key
            return defer.succeed(1)
        elif goodKey == 2: # AAHHHHH changed
            return defer.fail(error.ConchError('bad host key'))
        else:
            if options['host'] == self.transport.getPeer()[1]:
                host = options['host']
                khHost = options['host']
            else:
                host = '%s (%s)' % (options['host'], 
                                    self.transport.getPeer()[1])
                khHost = '%s,%s' % (options['host'], 
                                    self.transport.getPeer()[1])
            keyType = common.getNS(pubKey)[0]
            ques = """The authenticity of host '%s' can't be extablished.\r
%s key fingerprint is %s.""" % (host, 
                                {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType], 
                                fingerprint) 
            ques+='\r\nAre you sure you want to continue connecting (yes/no)? '
            return deferredAskFrame(ques, 1).addCallback(self._cbVerifyHostKey, pubKey, khHost, keyType)

    def _cbVerifyHostKey(self, ans, pubKey, khHost, keyType):
        if ans.lower() not in ('yes', 'no'):
            return deferredAskFrame("Please type  'yes' or 'no': ",1).addCallback(self._cbVerifyHostKey, pubKey, khHost, keyType)
        if ans.lower() == 'no':
            frame.write('Host key verification failed.\r\n')
            raise error.ConchError('bad host key')
        try:
            frame.write("Warning: Permanently added '%s' (%s) to the list of known hosts.\r\n" % (khHost, {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType]))
            known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'), 'a')
            print os.path.expanduser('~/.ssh/known_hosts')
            encodedKey = base64.encodestring(pubKey).replace('\n', '')
            known_hosts.write('\n%s %s %s' % (khHost, keyType, encodedKey))
            known_hosts.close()
        except:
            log.deferr()
            raise error.ConchError 

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
        print 'connection secure'
        if options['user']:
            user = options['user']
        else:
            user = getpass.getuser()
        self.requestService(SSHUserAuthClient(user, SSHConnection()))

class SSHUserAuthClient(userauth.SSHUserAuthClient):
    usedFiles = []

    def getPassword(self, prompt = None):
        if not prompt:
            prompt = "%s@%s's password: " % (self.user, options['host'])
        return deferredAskFrame(prompt,0) 

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
        try:
            return keys.getPublicKeyString(file) 
        except:
            return self.getPublicKey() # try again
    
    def getPrivateKey(self):
        file = os.path.expanduser(self.usedFiles[-1])
        if not os.path.exists(file):
            return None
        try:
            return defer.succeed(keys.getPrivateKeyObject(file))
        except keys.BadKeyError, e:
            if e.args[0] == 'encrypted key with no password':
                prompt = "Enter passphrase for key '%s': " % \
                       self.usedFiles[-1]
                return deferredAskFrame(prompt, 0).addCallback(self._cbGetPrivateKey, 0)
    def _cbGetPrivateKey(self, ans, count):
        file = os.path.expanduser(self.usedFiles[-1])
        try:
            return keys.getPrivateKeyObject(file, password = ans)
        except keys.BadKeyError:
            if count == 2:
                raise
            prompt = "Enter passphrase for key '%s': " % \
                   self.usedFiles[-1]
            return deferredAskFrame(prompt, 0).addCallback(self._cbGetPrivateKey, count+1)

class SSHConnection(connection.SSHConnection):
    def serviceStarted(self):
        if not options['noshell']:
            self.openChannel(SSHSession())
        if options.localForwards:
            for localPort, hostport in options.localForwards:
                reactor.listenTCP(localPort,
                            forwarding.SSHListenForwardingFactory(self, 
                                hostport,
                                forwarding.SSHListenClientForwardingChannel))
        if options.remoteForwards:
            for remotePort, hostport in options.remoteForwards:
                log.msg('asking for remote forwarding for %s:%s' %
                        (remotePort, hostport))
                data = forwarding.packGlobal_tcpip_forward(
                    ('0.0.0.0', remotePort))
                d = self.sendGlobalRequest('tcpip-forward', data)
                self.remoteForwards[remotePort] = hostport

class SSHSession(connection.SSHChannel):

    name = 'session'
    
    def channelOpen(self, foo):
        #global globalSession
        #globalSession = self
        # turn off local echo
        self.escapeMode = 1
        c = session.SSHSessionClient()
        if options['escape']:
            c.dataReceived = self.handleInput
        else:
            c.dataReceived = self.write
        c.connectionLost = self.sendEOF
        frame.callback = c.dataReceived
        frame.canvas.focus_force()
        if options['subsystem']:
            self.conn.sendRequest(self, 'subsystem', \
                common.NS(options['command']))
        elif options['command']:
            if options['tty']:
                term = os.environ.get('TERM', 'xterm')
                #winsz = fcntl.ioctl(fd, tty.TIOCGWINSZ, '12345678')
                winSize = (25,80,0,0) #struct.unpack('4H', winsz)
                ptyReqData = session.packRequest_pty_req(term, winSize, '')
                self.conn.sendRequest(self, 'pty-req', ptyReqData)                
            self.conn.sendRequest(self, 'exec', \
                common.NS(options['command']))
        else:
            if not options['notty']:
                term = os.environ.get('TERM', 'xterm')
                #winsz = fcntl.ioctl(fd, tty.TIOCGWINSZ, '12345678')
                winSize = (25,80,0,0) #struct.unpack('4H', winsz)
                ptyReqData = session.packRequest_pty_req(term, winSize, '')
                self.conn.sendRequest(self, 'pty-req', ptyReqData)
            self.conn.sendRequest(self, 'shell', '')
        self.conn.transport.transport.setTcpNoDelay(1)

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
        frame.write(data)

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

if __name__=="__main__":
    run()
