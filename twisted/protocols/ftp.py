
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

"""File Transfer Protocol support for Twisted Python.

The goal for this server is that it should be secure, high-performance, and
overloaded with stupid features.

TODO:

 * Authorization
   Anonymous are included
   User / Password is stored in a dict (factory.userdict) in plaintext
   Use cred
   Filelevel access
   Separate USER / PASS from mainloop

 * Ascii-download
   Currently binary only. Ignores TYPE

 * Missing commands
   HELP, REST, STAT, ...

 * Print out directory-specific messages
   As in READMEs etc

 * Testing
   Test at every ftp-program available
   And on any platform.

 * Security
   PORT needs to reply correctly if it fails
   The paths are done by os.path; but I should have something more generic
   (twisted.python.path anyone?)

 * Etc
   Documentation, Logging, Procedural content, Localization, Telnet PI,
   stop LIST from blocking...

DOCS:

 * Base information: RFC0959
 * Security: RFC2577
"""

# System Imports
import copy
import os
import time
import string
import types
import re
from math import floor

# Twisted Imports
from twisted.internet import abstract, tcp
from twisted.internet.interfaces import IProducer
from twisted.protocols import basic
from twisted.protocols import protocol
from twisted.protocols.protocol import ServerFactory
from twisted import internet
from twisted.python.defer import Deferred
from twisted.python.failure import Failure


# the replies from the ftp server
# a 3-digit number identifies the meaning
# used by Ftp.reply(key)
ftp_reply = {
    'file':      '150 File status okay; about to open data connection.',

    'type':      '200 Type set to %s.',
    'ok':        '200 %s command successful.',
    'size':      '213 %s',
    'syst':      '215 UNIX Type: L8',
    'abort':     '226 Abort successful',
    'welcome':   '220 Welcome, twisted.ftp at your service.',
    'goodbye':   '221 Goodbye.',
    'fileok':    '226 Transfer Complete.',
    'epsv':      '229 Entering Extended Passive Mode (|||%s|).',
    'cwdok':     '250 CWD command successful.',
    'pwd':       '257 "%s" is current directory.',

    'user':      '331 Password required for %s.',
    'userotp':   '331 Response to %s.',
    'guest':     '331 Guest login ok, type your name as password.',
    'userok':    '230 User %s logged in.',
    'guestok':   '230 Guest login ok, access restrictions apply.',

    'getabort':  '426 Transfer aborted.  Data connection closed.',
    'unknown':   "500 '%s': command not understood.",
    'nouser':    '503 Login with USER first.',
    'notimpl':   '504 Not implemented.',
    'nopass':    '530 Please login with USER and PASS.',
    'noauth':    '530 Sorry, Authentication failed.',
    'nodir':     '550 %s: No such file or directory.',
    'noperm':    '550 %s: Permission denied.'
    }



class SendFileTransfer:
    "Producer, server to client"
    
    request = None
    file = None
    filesize = None
    
    __implements__ = (IProducer,)
    
    def __init__(self, file, filesize, request):
        self.request = request
        self.file = file
        self.filesize = filesize
        request.registerProducer(self, 0) # TODO: Dirty
    
    def resumeProducing(self):
        if (self.request is None) or (self.file.closed):
            return
        self.request.write(self.file.read(abstract.FileDescriptor.bufferSize))
        
        if self.file.tell() == self.filesize:
            self.stopProducing()
            
    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.request.stopConsuming()
        self.request.finish()
        self.request = None


class DTP(protocol.Protocol):
    """A Client/Server-independent implementation of the DTP-protocol.
    Performs the actions RETR, STOR and LIST. The data transfer will
    start as soon as:
    1) The user has connected 2) the property 'action' has been set. 
    """
    # PI is the telnet-like interface to FTP
    # Will be set to the instance which initiates DTP
    pi = None
    file = None
    filesize = None
    action = ""

    def executeAction(self):
        """Initiates a transfer of data.
        Its action is based on self.action, and self.pi.queuedfile
        """
        if self.action == 'RETR':
           self.actionRETR(self.pi.queuedfile)
        if self.action == 'STOR':
           self.actionSTOR(self.pi.queuedfile) 
        if self.action == 'LIST':
           self.actionLIST(self.pi.queuedfile) # queuedfile now acts as a path

    def connectionMade(self):
        "Will start an transfer, if one is queued up, when the client connects"
        self.dtpPort = self.pi.dtpPort
        if self.action is not None:
            self.executeAction()

    def setAction(self, action):
        "Set the action, and if the connected, start the transfer"
        self.action = action
        if self.transport is not None:
            self.executeAction()

    def connectionLost(self):
        if (self.action == 'STOR') and (self.file):
            self.file.close()
            self.file = None
            self.pi.reply('fileok')
            self.pi.queuedfile = None
        self.action = None
        self.dtpPort.loseConnection()

    #
    #   "RETR"
    #
    def finishRETR(self):
        """Disconnect, and clean up a RETR
        Called by producer when the transfer is done
        """
        # Has _two_ checks if it is run when it is not connected; this logic
        # should be somewhere else.
        if self.file is not None:
            if self.file.tell() == self.filesize:
                self.pi.reply('fileok')
            else:
                self.pi.reply('getabort')
            self.file.close()
            self.file = None
        self.pi.queuedfile = None # just incase
        self.transport.loseConnection()

    def makeRETRTransport(self):
        transport = self.transport
        transport.finish = self.finishRETR
        return transport
        
    def actionRETR(self, queuedfile):
        "Send the given file to the peer"
        self.file = open(queuedfile, "rb")
        self.filesize = os.path.getsize(queuedfile)
        producer = SendFileTransfer(self.file, self.filesize, self.makeRETRTransport())
        producer.resumeProducing()

    #
    #   "STOR"
    #
    def dataReceived(self, data):
        if (self.action == 'STOR') and (self.file):
            self.file.write(data)
            self.filesize = self.filesize + len(data)

    def makeSTORTransport(self):
        transport = self.transport
        return transport
        
    def actionSTOR(self, queuedfile):
        "Retrieve a file from peer"
        self.file = open(queuedfile, "wb")
        self.filesize = 0
        transport = self.makeSTORTransport()

    #
    #   'LIST'
    #
    def actionLIST(self, dir):
        """Prints outs the files in the given directory
        Note that the printout is very fake, and only gives the filesize,
        date, time and filename.
        """
        list = os.listdir(dir)                
        for a in list:
            s = a
            ff = os.path.join(dir, s) # the full filename
            mtime = time.strftime("%b %d %H:%M", time.gmtime(os.path.getmtime(ff)))
            fsize = os.path.getsize(ff)
            if os.path.isdir(ff):
                diracc = 'd'
            else:
                diracc = '-'    
            self.transport.write(diracc+"r-xr-xr-x    1 twisted twisted %11d"
                                 % fsize+' '+mtime+' '+s+'\r\n')
        self.pi.reply('fileok')
        self.pi.queuedfile = None
        self.transport.loseConnection()

class DTPFactory(protocol.Factory):
    """The DTP-Factory.
    This class is not completely self-contained.
    """
    dtp = None      # The DTP-protocol
    dtpPort = None  # The TCPClient / TCPServer
    action = None

    def createPassiveServer(self):
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        # giving 0 will generate a free port
        self.dtpPort = tcp.Port(0, self)
        self.dtpPort.startListening()
 
    def createActiveServer(self):
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        self.dtp = self.buildProtocol(self.peerport)
        self.dtpPort = tcp.Client(self.peerhost, self.peerport, self.dtp)

    def buildProtocol(self,addr):
        p = DTP()
        p.factory = self
        p.pi = self
        self.dtp = p
        if self.action is not None:
            self.dtp.setAction(self.action)
            self.action = None
        return p

class FTP(basic.LineReceiver, DTPFactory):
    """The FTP-Protocol."""
    user   = None
    passwd = None
    root   = None
    wd     = None # Working Directory
    type   = None
    peerhost = None
    peerport = None
    queuedfile = None

    def setAction(self, action):
        """Alias for DTP.setAction
        Since there's no guarantee an instance of dtp exists"""
        if self.dtp is not None:
            self.dtp.setAction(action)
        else:
            self.action = action

    def reply(self, key, s = ''):
        if string.find(ftp_reply[key], '%s') > -1:
            print ftp_reply[key] % s + '\r\n'
            self.transport.write(ftp_reply[key] % s + '\r\n')
        else:
            print ftp_reply[key] + '\r\n'
            self.transport.write(ftp_reply[key] + '\r\n')
            
    # This command is IMPORTANT! Must also get rid of it :)
    def checkauth(self):
        """Will return None if the user has been authorized
        This must be run in front of all commands except USER, PASS and QUIT
        """
        if None in [self.user, self.passwd]:
            self.reply('nopass')
            return 1
        else:
            return None
        
    def connectionMade(self):
        self.reply('welcome')

    def ftp_Quit(self, params):
        self.reply('goodbye')
        self.transport.loseConnection()
    
    def ftp_User(self, params):
        """Get the login name, and reset the session
        PASS is expected to follow
        """
        if params=='':
            return 1
        self.user = string.split(params)[0]
        if self.factory.anonymous and self.user == self.factory.useranonymous:
            self.reply('guest')
            self.root = self.factory.root
            self.wd = '/'
        else:
            # TODO:
            # Add support for home-dir
            if self.factory.otp:
                otp = self.factory.userdict[self.user]["otp"]
                prompt = otp.challenge()
                otpquery = "Response to %s %s for skey" % (prompt, "required")
                self.reply('userotp', otpquery)
            else:
                self.reply('user', self.user)
            self.root = self.factory.root
            self.wd = '/'
        # Flush settings
        self.passwd = None
        self.type = 'A'
            
    def ftp_Pass(self, params):
        """Authorize the USER and the submitted password
        """
        if not self.user:
            self.reply('nouser')
            return
        self.passwd = params
        if self.user == self.factory.useranonymous:
            self.reply('guestok')
        else:
            # Authing follows
            if self.factory.otp:
                otp = self.factory.userdict[self.user]["otp"]
                try:
                    otp.authenticate(self.passwd)
                    self.reply('userok', self.user)
                except:
                    self.reply('noauth')
            else:
                if (self.factory.userdict.has_key(self.user)) and \
                   (self.factory.userdict[self.user]["passwd"] == self.passwd):
                    self.reply('userok', self.user)
                else:
                    self.reply('noauth')

    def ftp_Noop(self, params):
        """Do nothing, and reply an OK-message
        Sometimes used by clients to avoid a time-out.
        TODO: Add time-out, let Noop extend this time-out.
        Add a No-Transfer-Time-out as well to get rid of idlers.
        """
        if self.checkauth(): return
        self.reply('ok', 'NOOP')

    def ftp_Syst(self, params):
        """Return the running operating system to the client
        However, due to security-measures, it will return a standard 'L8' reply
        """
        if self.checkauth(): return
        self.reply('syst')
        
    def ftp_Pwd(self, params):
        if self.checkauth(): return
        self.reply('pwd', self.wd)

    def ftp_Cwd(self, params):
        if self.checkauth(): return
        wd = os.path.normpath(params)
        if not os.path.isabs(wd):
            wd = os.path.normpath(self.wd + '/' + wd)
        wd = string.replace(wd, '\\','/')
        while string.find(wd, '//') > -1:
            wd = string.replace(wd, '//','/')
        # '..', '\\', and '//' is there just to prevent stop hacking :P
        if (not os.path.isdir(self.root + wd)) or (string.find(wd, '..') > 0) or \
            (string.find(wd, '\\') > 0) or (string.find(wd, '//') > 0): 
            self.reply('nodir', params)
            return
        else:
            wd = string.replace(wd, '\\','/')
            self.wd = wd
            self.reply('cwdok')

    def ftp_Cdup(self, params):
        self.ftp_Cwd('..')

    def ftp_Type(self, params):
        if self.checkauth(): return
        params = string.upper(params)
        if params in ['A', 'I']:
            self.type = params
            self.reply('type', self.type)
        else:
            return 1

    def ftp_Port(self, params):
        """Request for an active connection
        This command may be potentially abused, and the only countermeasure
        so far is that no port below 1024 may be targeted.
        An extra approach is to disable port'ing to a third-party ip,
        which is optional through ALLOW_THIRDPARTY.
        Note that this disables 'Cross-ftp' 
        """
        if self.checkauth(): return
        params = string.split(params, ',')
        if not (len(params) in [6]): return 1
        peerhost = string.join(params[:4], '.') # extract ip
        peerport = int(params[4])*256+int(params[5])
        # Simple countermeasurements against bouncing
        if peerport < 1024:
            self.reply('notimpl')
            return
        if not self.factory.thirdparty:
            sockname = self.transport.getPeer()
            if not (peerhost == sockname[1]):
                self.reply('notimpl')
                return
        self.peerhost = peerhost
        self.peerport = peerport
        self.createActiveServer()
        self.reply('ok', 'PORT')

    def ftp_Pasv(self, params):
        "Request for a passive connection"
        if self.checkauth():
            return
        self.createPassiveServer()
        # Use the ip from the pi-connection
        sockname = self.transport.getHost()
        localip = string.replace(sockname[1], '.', ',')
        lport = self.dtpPort.socket.getsockname()[1]
        lp1 = lport / 256
        lp2, lp1 = str(lport - lp1*256), str(lp1)
        self.transport.write('227 Entering Passive Mode ('+localip+
                             ','+lp1+','+lp2+')\r\n')

    def ftp_Epsv(self, params):
        "Request for a Extended Passive connection"
        if self.checkauth(): 
            return
        self.createPassiveServer()
        self.reply('epsv', `self.dtpPort.socket.getsockname()[1]`)

    def buildFullpath(self, rpath):
        """Build a new path, from a relative path based on the current wd
        This routine is not fully tested, and I fear that it can be
        exploited by building clever paths
        """
        npath = os.path.normpath(rpath)
#        if npath == '':
#            npath = '/'
        if not os.path.isabs(npath):
            npath = os.path.normpath(self.wd + '/' + npath)
        npath = self.root + npath
        return os.path.normpath(npath) # finalize path appending 

    def ftp_Size(self, params):
        if self.checkauth():
            return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply('nodir', params)
            return
        self.reply('size', os.path.getsize(npath))

    def ftp_Dele(self, params):
        if self.checkauth():
            return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply('nodir', params)
            return
        os.remove(npath)
        self.reply('fileok')

    def ftp_Mkd(self, params):
        if self.checkauth():
            return
        npath = self.buildFullpath(params)
        try:
            os.mkdir(npath)
            self.reply('fileok')
        except IOError:
            self.reply('nodir')

    def ftp_Rmd(self, params):
        if self.checkauth():
            return
        npath = self.buildFullpath(params)
        if not os.path.isdir(npath):
            self.reply('nodir', params)
            return
        try:
            os.rmdir(npath)
            self.reply('fileok')
        except IOError:
            self.reply('nodir')
 
    def ftp_List(self, params):
        if self.checkauth():
            return
        if self.dtpPort is None:
            self.reply('notimpl')   # and will not be; standard noauth-reply
            return
        if params == "-a": params = '' # bug in konqueror
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if not os.path.isdir(npath):
            self.reply('nodir', params)
            return
        if not os.access(npath, os.O_RDONLY):
            self.reply('noperm', params)
            return
        self.reply('file')
        self.queuedfile = npath 
        self.setAction('LIST')
 
    def ftp_Retr(self, params):
        if self.checkauth():
            return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply('nodir', params)
            return
        if not os.access(npath, os.O_RDONLY):
            self.reply('noperm', params)
            return
        self.reply('file')
        self.queuedfile = npath 
        self.setAction('RETR')

    def ftp_Stor(self, params):
        if self.checkauth():
            return
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if os.path.isfile(npath):
            # Insert access for overwrite here :)
            #self.reply('nodir', params)
            pass
        self.reply('file')
        self.queuedfile = npath 
        self.setAction('STOR')

    def ftp_Abor(self, params):
        if self.checkauth():
            return
        if self.dtp.transport.connected:
            self.dtp.finishGet() # not 100 % perfect on uploads
        self.reply('abort')

    def lineReceived(self, line):
        "Process the input from the client"
        line = string.strip(line)
        print repr(line)
        command = string.split(line)
        if command == []:
            self.reply('unknown')
            return 0
        commandTmp, command = command[0], ''
        for c in commandTmp:
            if ord(c) < 128:
                command = command + c
        command = string.capitalize(command)
        print "-"+command+"-"
        if command == '':
            return 0
        if string.count(line, ' ') > 0:
            params = line[string.find(line, ' ')+1:]
        else:
            params = ''
        # Does this work at all? Quit at ctrl-D
        if ( string.find(line, "\x1A") > -1):
            command = 'Quit'
        method = getattr(self, "ftp_%s" % command, None)
        if method is not None:
            n = method(params)
            if n == 1:
                self.reply('unknown', string.upper(command))
        else:
            self.reply('unknown', string.upper(command))


class FTPFactory(protocol.Factory):
    command = ''
    userdict = {}
    anonymous = 0
    thirdparty = 0
    otp = 1
    root = '/usr/bin/local'
    useranonymous = 'anonymous'
 
    def buildProtocol(self, addr):
        p=FTP()
        p.factory = self
        return p


    
####
# And now for the client...

# Notes:
#   * Reference: http://cr.yp.to/ftp.html
#   * FIXME: Does not support pipelining (which is not supported by all
#     servers anyway).  This isn't a functionality limitation, just a
#     small performance issue.
#   * Only has a rudimentary understanding of FTP response codes (although
#     the full response is passed to the caller if they so choose).
#   * Assumes that USER and PASS should always be sent
#   * Always sets TYPE I  (binary mode)
#   * Doesn't understand any of the weird, obscure TELNET stuff (\377...)
#   * FIXME: Doesn't share any code with the FTPServer

class FTPDataPort(tcp.Port):
    def approveConnection(self, sock, addr):
        # FIXME: Guard against FTP spoofing
        return 1
    
    def fail(self, error):
        """Calls self.loseConnection
        
        Safe to call multiple times"""
        # TODO: Check that this really works...
        if self.connected:
            self.loseConnection()

class FTPError(Exception):
    pass

class ConnectionLost(FTPError):
    pass

class CommandFailed(FTPError):
    pass

class BadResponse(FTPError):
    pass

class UnexpectedResponse(FTPError):
    pass

class FTPCommand:
    def __init__(self, text=None):
        self.text = text
        self.deferred = Deferred()
        self.ready = 1
        
class FTPClient(basic.LineReceiver):
    debug = 0
    def __init__(self, username='anonymous', 
                 password='twisted@twistedmatrix.com',
                 passive=1):
        self.username = username
        self.password = password

        self.actionQueue = []
        self.nextDeferred = None
        self.queueLogin()
        self.response = []

        self.passive = passive

    def fail(self, error):
        """Disconnect, and also give an error to any queued deferreds"""
        self.transport.loseConnection()
        while self.actionQueue:
            ftpCommand = self.popCommandQueue()
            ftpCommand.deferred.errback(Failure(ConnectionLost('FTP connection lost', error)))

    def sendLine(self, line):
        if line is None:
            return
        basic.LineReceiver.sendLine(self, line)

    def sendNextCommand(self):
        ftpCommand = self.popCommandQueue()
        if ftpCommand is None:
            self.nextDeferred = None
            return
        if not ftpCommand.ready:
            self.actionQueue.insert(0, ftpCommand)
            internet.main.addTimeout(self.sendNextCommand, 1.0)
            self.nextDeferred = None
            return
        if ftpCommand.text == 'PORT':
            self.generatePortCommand(ftpCommand)
        if self.debug:
            print '<--', ftpCommand.text
        self.nextDeferred = ftpCommand.deferred
        self.sendLine(ftpCommand.text)

    def queueLogin(self):
        """Initialise the connection

        Login, send the password, set retrieval mode to binary"""
        self.nextDeferred = Deferred().addErrback(self.fail)
        self.nextDeferred.arm()
        for command in ('USER ' + self.username, 
                        'PASS ' + self.password,
                        'TYPE I',):
            ftpCommand = FTPCommand(command)
            self.queueCommand(ftpCommand)
            ftpCommand.deferred.addErrback(self.fail).arm()
        
    def queueCommand(self, ftpCommand):
        self.actionQueue.append(ftpCommand)
        if (len(self.actionQueue) == 1 and self.transport is not None and
            self.nextDeferred is None):
            self.sendNextCommand()

    def popCommandQueue(self):
        if self.actionQueue:
            return self.actionQueue.pop(0)
        else:
            return None

    def retrieve(self, command, protocol):
        """Retrieves a file or listing generated by the given command,
        feeding it to the given protocol.

        Returns a Deferred, which should be armed by the caller to ensure that
        the connection terminates properly."""
        if self.passive:
            # Hack: use a mutable object to sneak a variable out of the 
            # scope of doPassive
            _mutable = [None]
            def doPassive(response, 
                          self=self, mutable=_mutable, protocol=protocol):
                """Connect to the port specified in the response to PASV"""
                line = response[-1]

                abcdef = re.sub('[^0-9, ]', '', line[4:])
                a, b, c, d, e, f = map(string.strip,string.split(abcdef, ','))
                host = "%s.%s.%s.%s" % (a, b, c, d)
                port = int(e)*256 + int(f)

                mutable[0] = (tcp.Client(host, port, protocol, 30.0))

            pasvCmd = FTPCommand('PASV')
            self.queueCommand(pasvCmd)
            pasvCmd.deferred.addCallbacks(doPassive, self.fail).arm()

            cmd = FTPCommand(command)
            self.queueCommand(cmd)
            # Ensure the connection is always closed
            cmd.deferred.addCallbacks(
                lambda result, mutable=_mutable: mutable[0].loseConnection() or result,
                lambda result, mutable=_mutable: mutable[0].loseConnection())

            return cmd.deferred
        else:
            # We just place a marker command in the queue, and will fill in
            # the host and port numbers later (see generatePortCommand)
            portCmd = FTPCommand('PORT')
            portCmd.protocol = protocol
            portCmd.realDeferred = Deferred()
            portCmd.deferred.addErrback(portCmd.realDeferred.errback)
            self.queueCommand(portCmd)

            # Create dummy functions for the next callback to call.  
            # These will also be replaced with real functions in 
            # generatePortCommand.
            portCmd.loseConnection = lambda result: result
            portCmd.fail = lambda error: error
            
            cmd = FTPCommand(command)
            # Ensure that the connection always gets closed
            cmd.deferred.addErrback(portCmd.fail)

            self.queueCommand(cmd)
            return portCmd.realDeferred

    def generatePortCommand(self, portCmd):
        # Start listening on a port
        class FTPDataPortFactory(ServerFactory):
            def buildProtocol(self, connection):
                # This is a bit hackish -- we already have Protocol instance,
                # so just return it instead of making a new one
                self.protocol.factory = self
                return self.protocol
        FTPDataPortFactory.protocol = portCmd.protocol
        oldCL = portCmd.protocol.connectionLost
        def newCL(oldCL=oldCL, portCmd=portCmd):
            oldCL()
            portCmd.realDeferred.callback(portCmd.protocol)
        portCmd.protocol.connectionLost = newCL
        listener = FTPDataPort(0, FTPDataPortFactory())
        listener.deferred = portCmd.realDeferred
        listener.startListening()
        portCmd.fail = listener.fail

        # Construct crufty FTP magic numbers that represent host & port
        host = self.transport.getHost()[1]
        port = listener.getHost()[2]

        # Bleagh: port/256 isn't safe with Python 2.2's
        # "from __future__ import division", 
        # so we have to use int(floor(port/256)).  Yuck.  I would use
        # port//256, but that's not backwards-compatible.  This won't actually
        # be a problem until Python 2.3, but it's best to be future-proof...
        numbers = string.split(host, '.') + [str(int(floor(port/256))), 
                                             str(port%256)]
        portCmd.text = 'PORT ' + string.join(numbers,',')
        portCmd.deferred.addErrback(listener.fail).arm()

    def escapePath(self, path):
        # Escape newline characters
        return string.replace(path, '\n', '\0')

    def retrieveFile(self, path, protocol):
        return self.retrieve('RETR ' + self.escapePath(path), protocol)

    retr = retrieveFile

    def list(self, path, protocol):
        if path is None:
            path = ''
        return self.retrieve('LIST ' + self.escapePath(path), protocol)
        
    def nlst(self, path, protocol):
        if path is None:
            path = ''
        return self.retrieve('NLST ' + self.escapePath(path), protocol)

    def queueStringCommand(self, command):
        ftpCommand = FTPCommand(command)
        self.queueCommand(ftpCommand)
        return ftpCommand.deferred

    def cwd(self, path):
        return self.queueStringCommand('CWD ' + self.escapePath(path))

    def cdup(self):
        return self.queueStringCommand('CDUP')

    def pwd(self):
        return self.queueStringCommand('PWD')

    def quit(self):
        return self.queueStringCommand('QUIT')
    
    def lineReceived(self, line):
        # Add this line to the current response
        if self.debug:
            print '-->', line
        line = string.rstrip(line)
        self.response.append(line)

        code = line[0:3]
        
        # Bail out if this isn't the last line of a response
        # The last line of response starts with 3 digits followed by a space
        codeIsValid = len(filter(lambda c: c in '0123456789', code)) == 3
        if not (codeIsValid and line[3] == ' '):
            return

        # Ignore marks
        if code[0] == '1':
            return

        # Check that we were expecting a response
        if self.nextDeferred is None:
            self.fail(UnexpectedResponse(self.response))
            return

        # Reset the response
        response = self.response
        self.response = []

        # Look for a success or error code, and call the appropriate callback
        if code[0] in ('2', '3'):
            # Success
            self.nextDeferred.callback(response)
        elif code[0] in ('4', '5'):
            # Failure
            self.nextDeferred.errback(Failure(CommandFailed(response)))
        else:
            # This shouldn't happen unless something screwed up.
            print 'Server sent invalid response code %s' % (code,)
            self.nextDeferred.errback(Failure(BadResponse(response)))
            
        # Run the next command
        self.sendNextCommand()
        

class FTPFileListProtocol(basic.LineReceiver):
    # This is the evil required to match
    # "-rw-r--r--   1 root     other        531 Jan 29 03:26 README"
    # If you need different evil for a wacky FTP server, you can override this.
    fileLinePattern = re.compile(
        r'^(?P<filetype>.)(?P<perms>.{9})\s+\d*\s*'
        r'(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\d+)\s+'
        r'(?P<date>.*)\s+(?P<filename>.*)\r?$'
    )
    delimiter = '\n'

    def __init__(self):
        self.files = []

    def lineReceived(self, line):
        match = re.match(self.fileLinePattern, line)
        if match:
            dict = match.groupdict()
            dict['size'] = int(dict['size'])
            self.files.append(dict)

