
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
   Anonymous are included, but any user or password is accepted ATM.
   Create an abstract user-base

 * A better download-routine
   A producer/consumer setup

 * Upload
   Write-Access?

 * Ascii-download
   Currently binary only. Ignores TYPE

 * Missing commands
   HELP, REST, ...

 * Print out directory-specific messages
   As in READMEs etc

 * Testing
   Test at every ftp-program available
   And on any platform.

 * Security
   PORT needs to reply correctly if it fails

 * Configuration
   All config is now through BOLD_CASE_CONSTANTS(tm)

 * Etc
   Documentation, Logging, Procedural content, Localization...

DOCS:

 * Base information: RFC0959
 * Security: RFC2577
"""

# System Imports
import copy
import traceback
import os
import time

# Twisted Imports
from twisted.internet import abstract, tcp
from twisted.protocols import basic
from twisted.protocols import protocol
from twisted.python import threadable

ALLOW_ANONYMOUS = 1
# The next option enables 'PORT' to connect to a arbitrary port
# Should not be enabled by default, but for testing it is
ALLOW_THIRDPARTY = 1
USER_ANONYMOUS = 'anonymous'
FTP_ROOT = '/usr/local/ftp'
if os.name == 'nt':
    FTP_ROOT = 'c:/temp'

# the replies from the ftp server
# a 3-digit number identifies the meaning
# used by Ftp.reply(key)
ftp_reply = {
    'get':       '150 File status okay; about to open data connection.',
    'type':      '200 Type set to %s.',
    'ok':        '200 %s command successful.',
    'size':      '213 %s',
    'syst':      '215 UNIX Type: L8',
    'abort':     '226 Abort successful',
    'welcome':   '220 Welcome, twisted.ftp at your service.',
    'goodbye':   '221 Goodbye.',
    'getok':     '226 Transfer Complete.',
    'epsv':      '229 Entering Extended Passive Mode (|||%s|).',
    'cwdok':     '250 CWD command successful.',
    'pwd':       '257 "%s" is current directory.',
    'user':      '331 Password required for %s.',
    'guest':     '331 Guest login ok, type your name as password.',
    'userok':    '230 User %s logged in.',
    'guestok':   '230 Guest login ok, access restrictions apply.',
    'getabort':  '426 Transfer aborted.  Data connection closed.',
    'unknown':   "500 '%s': command not understood.",
    'nouser':    '503 Login with USER first.',
    'notimpl':   '504 Not implemented',
    'noauth':    '530 Please login with USER and PASS.',
    'nodir':     '550 %s: No such file or directory.'
    }

class FileTransfer:
    request = None
    file = None
    filesize = None

    def __init__(self, file, filesize, request):
        self.request = request
        self.file = file
        self.filesize = filesize

class sendFileTransfer(FileTransfer):
    "Producer, server to client"
    def __init__(self, *args, **kw):
        apply(FileTransfer.__init__,((self,)+args),kw)
        args[2].registerProducer(self, 0) # TODO: Dirty
    
    def resumeProducing(self):
        if (self.request is None) or (self.file.closed):
            return
        self.request.write(self.file.read(abstract.FileDescriptor.bufferSize))

        if self.file.tell() == self.filesize:
            print "very finished"
            self.request.finish()
#            self.request.loseConnection()
            self.request = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.request = None

    synchronized = ['resumeProducing', 'stopProducing']

threadable.synchronize(sendFileTransfer)

class DTP(protocol.Protocol):
    """A Client/Server-independent implementation of the DTP-protocol.
    Is able to GET and LIST in an ftp-environment

    imminent total rewrite
    """
    # PI is the telnet-like interface to FTP
    # Will be set to the instance which initiates DTP
    pi = None
    file = None
    filesize = None

   # def __init__(self):
   #     pass

    def loseConnection(self):
        "Disconnect, and clean up"
        print "disconcert and die"
        if self.file is not None:
            if self.file.tell() == self.filesize:
                self.pi.reply('getok')
            else:
                self.pi.reply('getabort')
            self.file.close()
            self.file = None
        self.pi.queuedfile = None # just incase
        self.transport.loseConnection()

    def finish(self):
        self.loseConnection()

    def makeTransport(self):
        print "makeTransport"
        transport = self.transport
        transport.finish = self.finish
        return transport
        
    def connectionMade(self):
        "Will start an transfer, if one is queued up, when the client connects"
        print "connectionMade"
        if self.pi.action is not None:
            self.executeAction()

    def executeAction(self):
        """Initiates the transfer.
        This is a two-case implementation for starting the transfer.
        It is either started by the telnet-interface when the connection
        is already open, or it is called by connectionMade.
        The property 'pi' is the telnetconnection and its property 'action'
        can either be 'GET', 'PUT', or 'LIST'. Pretty lame, eh? :)
        """
        print "executeaction"
        if self.pi.action == 'GET':
           self.fileget(self.pi.queuedfile)
        if self.pi.action == 'PUT':
           self.fileput(self.pi.queuedfile) 
        if self.pi.action == 'LIST':
           self.listdir(self.pi.queuedfile) # queuedfile now acts as a path :)
        self.pi.action = None

    def fileget(self, queuedfile):
        "Send the given file to the peer"
        self.file = open(queuedfile, "rb")
        self.filesize = os.path.getsize(queuedfile)
        sendFileTransfer(self.file, self.filesize, self.makeTransport())

    def fileput(self, queuedfile):
        raise NotImplementedError

    def listdir(self, dir):
        """Prints outs the files in the given directory
        Note that the printout is very fake, and only gives the filesize,
        date, time and filename.
        """
        list = os.listdir(dir)                
        for a in list:
            s = a
            ff = os.path.join(dir, s) # the full filename
            mtime = time.strftime("%b %2d %2H:%2M",
                                  time.gmtime(os.path.getmtime(ff)))
            fsize = os.path.getsize(ff)
            if os.path.isdir(ff):
                diracc = 'd'
            else:
                diracc = '-'    
            self.transport.write(diracc+"r-xr-xr-x    1 twisted twisted %11d"
                                 % fsize+' '+mtime+' '+s+'\r\n')
        self.pi.reply('getok')
        self.pi.queuedfile = None
        self.transport.loseConnection()

class FTP(protocol.Protocol):
    user   = None
    passwd = None
    root   = None
    wd     = None # Working Directory
    type   = None
    peerhost = None
    peerport = None
    dtp = None      # The DTP-protocol
    dtpPort = None  # The TCPClient / TCPServer
    action = None
    queuedfile = None

    def reply(self, key, s = ''):
        print key
        if ftp_reply[key].find('%s') > -1:
            self.transport.write(ftp_reply[key] % s + '\r\n')
        else:
            self.transport.write(ftp_reply[key] + '\r\n')
            
    # This command is IMPORTANT! Must also get rid of it :)
    def checkauth(self):
        """Will return None if the user has been authorized
        This must be run in front of all commands except USER, PASS and QUIT
        """
        if None in [self.user, self.passwd]:
            self.reply('noauth')
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
        self.user = params.split()[0]
        if ALLOW_ANONYMOUS and self.user == USER_ANONYMOUS:
            self.reply('guest')
            self.root = FTP_ROOT
            self.wd = '/'
        else:
            # TODO:
            # Add support for home-dir
            self.reply('user', self.user)
            self.root = FTP_ROOT
            self.wd = '/'
        # Flush settings
        self.passwd = None
        self.type = 'A'
            
    def ftp_Pass(self, params):
        """Authorize the USER and the submitted password
        Password authorization is not implemented.
        """
        # todo:
        # Add authorizing
        if not self.user:
            self.reply('nouser')
            return
        self.passwd = params
        if self.user == USER_ANONYMOUS:
            self.reply('guestok')
        else:
            self.reply('userok', self.user)

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
        if not os.path.isdir(self.root + wd):
            self.reply('nodir', params)
            return
        else:
            self.wd = wd
            self.reply('cwdok')

    def ftp_Cdup(self, params):
        self.ftp_Cwd('..')

    def ftp_Type(self, params):
        if self.checkauth(): return
        params = params.upper()
        if params in ['A', 'I']:
            self.type = params
            self.reply('type', self.type)
        else:
            return 1

    def createPassiveServer(self):
        # a bit silly code
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        # giving 0 will generate a free port
        self.dtpPort = tcp.Port(0, self)
        self.dtpPort.startListening()
 
    def createActiveServer(self):
        # silly code repeating
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        self.dtpPort = tcp.Client(self.peerhost, self.peerport,
                                  self.buildProtocol(self.peerport))
        self.dtp.transport = self.dtpPort

    def buildProtocol(self, addr):
        self.dtp = DTP()
        self.dtp.pi = self
        self.dtp.factory = self
        return self.dtp

    def ftp_Port(self, params):
        """Request for an active connection
        This command may be potentially abused, and the only countermeasure
        so far is that no port below 1024 may be targeted.
        An extra approach is to disable port'ing to a third-party ip,
        which is optional through ALLOW_THIRDPARTY.
        Note that this disables 'Cross-ftp' 
        """
        if self.checkauth(): return
        params = params.split(',')
        if not (len(params) in [6]): return 1
        peerhost = '.'.join(params[:4]) # extract ip
        peerport = int(params[4])*256+int(params[5])
        # Simple countermeasurements against bouncing 
        if self.peerport < 1024:
            self.reply('notimpl')
        if not ALLOW_THIRDPARTY:
            sockname = self.transport.getPeer()
            if not (peerhost == sockname[1]):
                self.reply('notimpl')
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
        localip = sockname[1].replace('.', ',')
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
        if npath == '':
            npath = '/'
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
 
    def ftp_List(self, params):
        if self.checkauth():
            return
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if not os.path.isdir(npath):
            self.reply('nodir', params)
            return
        self.reply('get')
        self.queuedfile = npath 
        self.action = 'LIST'
        print self.dtp, "is the DTP"
        print self.dtp.transport, "is the Transport"
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.executeAction()

    def ftp_Retr(self, params):
        if self.checkauth():
            return
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply('nodir', params)
            return
        self.reply('get')
        self.queuedfile = npath 
        self.action = 'GET'
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.executeAction()

    def ftp_Abor(self, params):
        if self.checkauth():
            return
        if self.dtp.transport.connected:
            self.dtp.loseConnection()
        self.reply('abort')

    def processLine(self, line):
        "Process the input from the client"
        line = line.strip()
        print line
        command = line.split()
        if command == []:
            self.reply('unknown')
            return 0
        commandTmp, command = command[0], ''
        for c in commandTmp:
            if ord(c) < 128:
                command = command + c
        command = command.capitalize()
        print "-"+command+"-"
        if command == '':
            return 0
        if line.count(' ') > 0:
            params = line[line.find(' ')+1:]
        else:
            params = ''
        if ( line.find("\x1A") > -1):
            command = 'Quit'
        method = getattr(self, "ftp_%s" % command, None)
        if method is not None:
            n = method(params)
            if n == 1:
                self.reply('unknown', command.upper())
        else:
            self.reply('unknown', command.upper())

    def dataReceived(self, line):
        self.processLine(line)
        return 0
        
                  
class ShellFactory(protocol.Factory):
    command = ''
    done = None
    parent = None

    def buildProtocol(self, addr):
        p=FTP()
        p.factory = self
        return p
