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
# $Id: conch.py,v 1.53 2003/04/19 03:22:48 acapnotic Exp $

#""" Implementation module for the `conch` command.
#"""

from twisted.conch.error import ConchError
from twisted.conch.ssh import transport, userauth, connection, common, keys
from twisted.conch.ssh import session, forwarding, channel
from twisted.internet import reactor, stdio, defer, protocol
from twisted.internet.error import CannotListenError
from twisted.python import usage, log, util
from twisted.spread import banana

import os, sys, getpass, struct, tty, fcntl, base64, signal, stat, cPickle

class GeneralOptions(usage.Options):
    synopsis = """Usage:    conch [options] host [command]
 """

    optParameters = [['user', 'l', None, 'Log in using this user name.'],
                    ['identity', 'i', None],
                    ['escape', 'e', '~'],
                    ['cipher', 'c', None],
                    ['macs', 'm', None],
                    ['port', 'p', None, 'Connect to this port.  Server must be on the same port.'],
                    ['localforward', 'L', None, 'listen-port:host:port   Forward local port to remote address'],
                    ['remoteforward', 'R', None, 'listen-port:host:port   Forward remote port to local address'],
                    ['option', 'o', None, 'Ignored OpenSSH options'],
                    ]

    optFlags = [['null', 'n', 'Redirect input from /dev/null.'],
                ['fork', 'f', 'Fork to background after authentication.'],
                ['tty', 't', 'Tty; allocate a tty even if command is given.'],
                ['notty', 'T', 'Do not allocate a tty.'],
                ['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['noshell', 'N', 'Do not execute a shell or command.'],
                ['subsystem', 's', 'Invoke command (mandatory) as SSH2 subsystem.'],
                ['log', 'v', 'Log to stderr'],
                ['nocache', 'I', 'Do not use an already existing connection if it exists.'],
                ['nox11', 'x']]

    identitys = []
    localForwards = []
    remoteForwards = []

    def opt_identity(self, i):
        """Identity for public-key authentication"""
        self.identitys.append(i)

    def opt_escape(self, esc):
        "Set escape character; ``none'' = disable"
        if esc == 'none':
            self['escape'] = None
        elif esc[0] == '^' and len(esc) == 2:
            self['escape'] = chr(ord(esc[1])-64)
        elif len(esc) == 1:
            self['escape'] = esc
        else:
            sys.exit("Bad escape character '%s'." % esc)

    def opt_cipher(self, cipher):
        "Select encryption algorithm"
        if cipher in SSHClientTransport.supportedCiphers:
            SSHClientTransport.supportedCiphers = [cipher]
        else:
            sys.exit("Unknown cipher type '%s'" % cipher)

    def opt_macs(self, mac):
        "Specify MAC algorithms"
        if mac in SSHClientTransport.supportedMACs:
            SSHClientTransport.supportedMACs = [mac]
        else:
            sys.exit("Unknown mac type '%s'" % mac)

    def opt_localforward(self, f):
        "Forward local port to remote address (lport:host:port)"
        localPort, remoteHost, remotePort = f.split(':') # doesn't do v6 yet
        localPort = int(localPort)
        remotePort = int(remotePort)
        self.localForwards.append((localPort, (remoteHost, remotePort)))

    def opt_remoteforward(self, f):
        """Forward remote port to local address (rport:host:port)"""
        remotePort, connHost, connPort = f.split(':') # doesn't do v6 yet
        remotePort = int(remotePort)
        connPort = int(connPort)
        self.remoteForwards.append((remotePort, (connHost, connPort)))

    def opt_compress(self):
        "Enable compression"
        SSHClientTransport.supportedCompressions[0:1] = ['zlib']

    def parseArgs(self, host, *command):
        self['host'] = host
        self['command'] = ' '.join(command)

# Rest of code in "run"
options = None
conn = None
exitStatus = 0

def run():
    global options
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
    if not options['user']:
        options['user'] = getpass.getuser()
    if not options['port']:
        options['port'] = 22
    else:
        options['port'] = int(options['port'])
    log.msg((options['host'],options['port']))
    filename = os.path.expanduser("~/.conch-%(user)s-%(host)s-%(port)s" % options)
    log.msg(filename)
    if not options['nocache'] and os.path.exists(filename):
        reactor.connectUNIX(filename, SSHUnixClientFactory(), timeout=2)
    else:
        reactor.connectTCP(options['host'], options['port'], SSHClientFactory())
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
    if sys.stdout.isatty():
        print 'Connection to %s closed.' % options['host']
    sys.exit(exitStatus)

def handleError():
    from twisted.python import failure
    global exitStatus
    exitStatus = 2
    reactor.stop()
    log.err(failure.Failure())
    raise

def onConnect():
    if not options['noshell']:
        conn.openChannel(SSHSession())
    if options.localForwards:
        for localPort, hostport in options.localForwards:
            reactor.listenTCP(localPort,
                        forwarding.SSHListenForwardingFactory(conn,
                            hostport,
                            SSHListenClientForwardingChannel))
    if options.remoteForwards:
        for remotePort, hostport in options.remoteForwards:
            log.msg('asking for remote forwarding for %s:%s' %
                    (remotePort, hostport))
            data = forwarding.packGlobal_tcpip_forward(
                ('0.0.0.0', remotePort))
            d = conn.sendGlobalRequest('tcpip-forward', data)
            conn.remoteForwards[remotePort] = hostport
    if options['fork']:
        if os.fork():
            os._exit(0)
        os.setsid()
        for i in range(3):
            try:
                os.close(i)
            except OSError, e:
                import errno
                if e.errno != errno.EBADF:
                    raise

    if isinstance(conn, SSHConnection) and not options['nocache']:
        filename = os.path.expanduser("~/.conch-%(user)s-%(host)s-%(port)s" % options)
        try:
            reactor.listenUNIX(filename, SSHUnixServerFactory(), mode = 0600)
        except CannotListenError:
            pass # we'll just not listen, not a big deal

class SSHUnixClientFactory(protocol.ClientFactory):
    noisy = 1

    def clientConnectionLost(self, connector, reason):
        reactor.stop()

    def clientConnectionFailed(self, connector, reason):
        os.unlink(connector.transport.addr)
        reactor.connectTCP(options['host'], options['port'], SSHClientFactory())

    def startedConnecting(self, connector):
        fd = connector.transport.fileno()
        stats = os.fstat(fd)
        filestats = os.stat(connector.transport.addr)
        if stat.S_IMODE(filestats[0]) != 0600:
            log.msg("socket mode is not 0600: %s" % oct(stat.S_IMODE(stats[0])))
        elif filestats[4] != os.getuid():
            log.msg("socket not owned by us: %s" % stats[4])
        elif filestats[5] != os.getgid():
            log.msg("socket not owned by our group: %s" % stats[5])
        # XXX reenable this when i can fix it for cygwin
        #elif filestats[-3:] != stats[-3:]:
        #    log.msg("socket doesn't have same create times")
        else:
            log.msg('conecting OK')
            return
        connector.stopConnecting()

    def buildProtocol(self, addr):
        return SSHUnixClientProtocol()

class SSHUnixServerFactory(protocol.Factory):

    def buildProtocol(self, addr):
        return SSHUnixServerProtocol()

class SSHUnixClientProtocol(banana.Banana):
    knownDialects = ['none']

    def __init__(self):
        banana.Banana.__init__(self)
        self.channelQueue = []
        self.channels = {}
        self.deferredQueue = []
        self.deferreds = {}

    def connectionReady(self):
        global conn
        conn = self
        onConnect()

    def expressionReceived(self, lst):
        vocabName = lst[0]
        fn = "client_%s" % vocabName
        func = getattr(self, fn)
        func(lst[1:])

    def sendMessage(self, vocabName, *tup):
        self.sendEncoded([vocabName] + list(tup))

    def returnDeferred(self):
        d = defer.Deferred()
        self.deferredQueue.append(d)
        return d

    def moveDeferred(self, dn):
        self.deferreds[dn] = self.deferredQueue.pop(0)

    def sendGlobalRequest(self, request, data, wantReply = 0):
        self.sendMessage('sendGlobalRequest', request, data, wantReply)
        if wantReply:
            return self.returnDeferred()

    def openChannel(self, channel, extra = ''):
        self.channelQueue.append(channel)
        channel.conn = self
        self.sendMessage('openChannel', channel.name,
                                        channel.localWindowSize,
                                        channel.localMaxPacket, extra)

    def sendRequest(self, channel, requestType, data, wantReply = 0):
        self.sendMessage('sendRequest', channel.id, requestType, data, wantReply)
        if wantReply:
            self.returnDeferred()

    def adjustWindow(self, channel, bytesToAdd):
        self.sendMessage('adjustWindow', channel.id, bytesToAdd)

    def sendData(self, channel, data):
        self.sendMessage('sendData', channel.id, data)

    def sendExtendedData(self, channel, dataType, data):
        self.sendMessage('sendExtendedData', channel.id, data)

    def sendEOF(self, channel):
        self.sendMessage('sendEOF', channel.id)

    def sendClose(self, channel):
        self.sendMessage('sendClose', channel.id)

    def client_returnDeferred(self, lst):
        deferredID = lst[0]
        self.deferreds[deferredID] = self.deferredQueue.pop(0)

    def client_callbackDeferred(self, lst):
        deferredID, result = lst
        d = self.deferreds[deferredID]
        del self.deferreds[deferredID]
        d.callback(cPickle.loads(result))

    def client_errbackDeferred(self, lst):
        deferredID, result = lst
        d = self.deferreds[deferredID]
        del self.deferreds[deferredID]
        d.errback(cPickle.loads(result))

    def client_channelID(self, lst):
        channelID = lst[0]
        self.channels[channelID] = self.channelQueue.pop(0)
        self.channels[channelID].id = channelID

    def client_channelOpen(self, lst):
        channelID, remoteWindow, remoteMax, specificData = lst
        channel = self.channels[channelID]
        channel.remoteWindowLeft = remoteWindow
        channel.remoteMaxPacket = remoteMax
        channel.channelOpen(specificData)

    def client_openFailed(self, lst):
        channelID, reason = lst
        self.channels[channelID].openFailed(cPickle.loads(reason))
        del self.channels[channelID]

    def client_addWindowBytes(self, lst):
        channelID, bytes = lst
        self.channels[channelID].addWindowBytes(bytes)

#    def client_requestReceived(self, lst):
#        channelID, requestType, data = lst
#        d = self.channels[channelID].requestReceived(requestType, data)
#        assert not isintance(d, defer.Deferred)
#        self.sendMessage("requestResponse", channelID, requestType, d)

    def client_dataReceived(self, lst):
        channelID, data = lst
        self.channels[channelID].dataReceived(data)

    def client_extReceived(self, lst):
        channelID, dataType, data = lst
        self.channels[channelID].extReceived(dataType, data)

    def client_eofReceived(self, lst):
        channelID = lst[0]
        self.channels[channelID].eofReceived()

    def client_closed(self, lst):
        channelID = lst[0]
        self.channels[channelID].closed()
        del self.channels[channelID]

class SSHUnixServerProtocol(banana.Banana):
    def __init__(self):
        banana.Banana.__init__(self, 0)
        self.deferredID = 0

    def expressionReceived(self, lst):
        vocabName = lst[0]
        fn = "server_%s" % vocabName
        func = getattr(self, fn)
        func(lst[1:])

    def sendMessage(self, vocabName, *tup):
        self.sendEncoded([vocabName] + list(tup))

    def returnDeferred(self, d):
        di = self.deferredID
        self.deferredID += 1
        d.addCallback(self._cbDeferred, di)
        d.addErrback(self._ebDeferred, di)
        self.sendMessage('returnDeferred', di)

    def _cbDeferred(self, result, di):
        self.sendMessage('callbackDeferred', di, result)

    def _ebDeferred(self, reason, di):
        self.sendMessage('errbackDeferred', di, cPickle.dumps(reason))

    def haveChannel(self, channelID):
        return conn.channels.has_key(channelID)

    def getChannel(self, channelID):
        channel = conn.channels[channelID]
        if not isinstance(channel, SSHUnixChannel):
            raise ConchError('nice try bub')
        return channel

    def server_sendGlobalRequest(self, lst):
        requestName, data, wantReply = lst
        d = conn.sendGlobalRequest(requestName, data, wantReply)
        if wantReply:
            self.returnDeferred(d)

    def server_openChannel(self, lst):
        name, windowSize, maxPacket, extra = lst
        channel = SSHUnixChannel(self, name, windowSize, maxPacket)
        conn.openChannel(channel, extra)
        self.sendMessage('channelID', channel.id)

    def server_sendRequest(self, lst):
        cn, requestType, data, wantReply = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        d = conn.sendRequest(channel, requestType, data, wantReply)
        if wantReply:
            self.returnDeferred(d)

    def server_adjustWindow(self, lst):
        cn, bytesToAdd = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        conn.adjustWindow(channel, bytesToAdd)

    def server_sendData(self, lst):
        cn, data = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        conn.sendData(channel, data)

    def server_sendExtended(self, lst):
        cn, dataType, data = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        conn.sendExtendedData(channel, dataType, data)

    def server_sendEOF(self, lst):
        (cn, ) = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        conn.sendEOF(channel)

    def server_sendClose(self, lst):
        (cn, ) = lst
        if not self.haveChannel(cn): return
        channel = self.getChannel(cn)
        conn.sendClose(channel)

class SSHUnixChannel(channel.SSHChannel):
    def __init__(self, unix, name, windowSize, maxPacket):
        channel.SSHChannel.__init__(self, windowSize, maxPacket, conn = conn)
        self.unix = unix
        self.name = name

    def channelOpen(self, specificData):
        self.unix.sendMessage('channelOpen', self.id, self.remoteWindowLeft,
                                             self.remoteMaxPacket, specificData)

    def openFailed(self, reason):
        self.unix.sendMessage('openFailed', self.id, cPickle.dumps(reason))

    def addWindowBytes(self, bytes):
        self.unix.sendMessage('addWindowBytes', self.id, bytes)

    def dataReceived(self, data):
        self.unix.sendMessage('dataReceived', self.id, data)

    def extReceived(self, dataType, data):
        self.unix.sendMessage('extReceived', self.id, dataType, data)

    def eofReceived(self):
        self.unix.sendMessage('eofReceived', self.id)

    def closed(self):
        self.unix.sendMessage('closed', self.id)
        if len(conn.channels) == 1 and not (options['noshell'] and not options['nocache']): # just us left
            reactor.stop()

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
        goodKey = self.isInKnownHosts(options['host'], pubKey)
        if goodKey == 1: # good key
            return defer.succeed(1)
        elif goodKey == 2: # AAHHHHH changed
            return defer.fail(ConchError('changed host key'))
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
                return defer.fail(ConchError('bad host key'))
            print "Warning: Permanently added '%s' (%s) to the list of known hosts." % (khHost, {'ssh-dss':'DSA', 'ssh-rsa':'RSA'}[keyType])
            known_hosts = open(os.path.expanduser('~/.ssh/known_hosts'), 'a')
            encodedKey = base64.encodestring(pubKey).replace('\n', '')
            known_hosts.write('\n%s %s %s' % (khHost, keyType, encodedKey))
            known_hosts.close()
            return defer.succeed(1)

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
        self.requestService(SSHUserAuthClient(options['user'], SSHConnection()))

class SSHUserAuthClient(userauth.SSHUserAuthClient):
    usedFiles = []

    def getPassword(self, prompt = None):
        if not prompt:
            prompt = "%s@%s's password: " % (self.user, options['host'])
        try:
            return defer.succeed(util.getPassword(prompt))
        except KeyboardInterrupt, e:
            print
            reactor.stop()
            return defer.fail(ConchError('PEBKAC'))

    def getPublicKey(self):
        files = [x for x in options.identitys if x not in self.usedFiles]
        log.msg(str(options.identitys))
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

    def getPrivateKey(self):
        file = os.path.expanduser(self.usedFiles[-1])
        if not os.path.exists(file):
            return None
        try:
            return defer.succeed(keys.getPrivateKeyObject(file))
        except keys.BadKeyError, e:
            if e.args[0] == 'encrypted key with no password':
                for i in range(3):
                    prompt = "Enter passphrase for key '%s': " % \
                           self.usedFiles[-1]
                    p = util.getPassword(prompt)
                    try:
                        return defer.succeed(keys.getPrivateKeyObject(file, password = p))
                    except keys.BadKeyError:
                        pass
                return defer.fail(ConchError('bad password'))
            raise
        except KeyboardError:
            print
            reactor.stop()

class SSHConnection(connection.SSHConnection):
    def serviceStarted(self):
        global conn
        conn = self
        onConnect()

    def global_forwarded_tcp(self, windowSize, maxPacket, data):
        remoteHP, origHP = forwarding.unpackOpen_forwarded_tcp(data)
        if self.remoteForwards.has_key(remoteHP[1]):
            connectHP = self.remoteForwards[remoteHP[1]]
            return SSHConnectForwardingChannel(connectHP,
                                            remoteWindow = windowSize,
                                            remoteMaxPacket = maxPacket,
                                            conn = self)
        else:
            return OPEN_CONNECT_FAILED, "don't know about that port"

class SSHSession(channel.SSHChannel):

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
        self.stdio = stdio.StandardIO(c)
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
            if hasattr(self.conn.transport, 'transport'):
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
            elif char == '#': # display connections
                self.stdio.write('\r\nThe following connections are open:\r\n')
                channels = self.conn.channels.keys()
                channels.sort()
                for channelId in channels:
                    self.stdio.write('  #%i %s\r\n' % (channelId, str(self.conn.channels[channelId])))
                return
            self.write('~' + char)
        else:
            self.escapeMode = 0
            self.write(char)

    def dataReceived(self, data):
        self.stdio.write(data)

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
        if len(self.conn.channels) == 1 and not (options['noshell'] and not options['nocache']): # just us left
            reactor.stop()

    def request_exit_status(self, data):
        global exitStatus
        exitStatus = int(struct.unpack('>L', data)[0])
        log.msg('exit status: %s' % exitStatus)

    def sendEOF(self):
        self.conn.sendEOF(self)

    def stopWriting(self):
        self.stdio.stopReading()

    def startWriting(self):
        self.stdio.startReading()

class SSHListenClientForwardingChannel(forwarding.SSHListenClientForwardingChannel):

    def closed(self):
        forwarding.SSHListenClientForwardingChannel.closed(self)
        if len(self.conn.channels) == 1 and not (options['noshell'] and not options['nocache']): # just us left
            reactor.stop()

class SSHConnectForwardingChannel(forwarding.SSHConnectForwardingChannel):

    def closed(self):
        forwarding.SSHConnectForwardingChannel.closed(self)
        if len(self.conn.channels) == 1 and not (options['noshell'] and not options['nocache']): # just us left
            reactor.stop()
