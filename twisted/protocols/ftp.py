
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

# Twisted Imports
from twisted.internet import abstract, tcp
from twisted.internet.interfaces import IProducer
from twisted.protocols import basic
from twisted.protocols import protocol

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
    'nodir':     '550 %s: No such file or directory.'
    }



class sendFileTransfer:
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
        producer = sendFileTransfer(self.file, self.filesize, self.makeRETRTransport())
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
    thirdpart = 0
    otp = 1
    root = '/usr/bin/local'
    useranonymous = 'anonymous'
 
    def buildProtocol(self, addr):
        p=FTP()
        p.factory = self
        return p
