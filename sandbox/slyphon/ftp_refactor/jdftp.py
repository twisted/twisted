#!/usr/bin/env python2.3

# System Imports
import os
import time
import string
import types
import re
import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter
from twisted import internet
from twisted.internet.defer import Deferred, DeferredList, FAILURE
from twisted.python.failure import Failure
from twisted.python import log, components

from twisted.cred import error
from twisted.cred import portal
from twisted.cred import credentials

# response codes

RESTART_MARKER_REPLY                    = 100
SERVICE_READY_IN_N_MINUTES              = 120
DATA_CNX_ALREADY_OPEN_START_XFR         = 125
FILE_STATUS_OK_OPEN_DATA_CNX            = 150

CMD_OK                                  = 200.1
TYPE_SET_OK                             = 200.2
CMD_NOT_IMPLMNTD_SUPERFLUOUS            = 202
SYS_STATUS_OR_HELP_REPLY                = 211
DIR_STATUS                              = 212
FILE_STATUS                             = 213
HELP_MSG                                = 214
NAME_SYS_TYPE                           = 215
SVC_READY_FOR_NEW_USER                  = 220.1
WELCOME_MSG                             = 220.2
SVC_CLOSING_CTRL_CNX                    = 221
GOODBYE_MSG                             = 221
DATA_CNX_OPEN_NO_XFR_IN_PROGRESS        = 225
CLOSING_DATA_CNX                        = 226
TXFR_COMPLETE_OK                        = 226
ENTERING_PASV_MODE                      = 227
ENTERING_EPSV_MODE                      = 229
USR_LOGGED_IN_PROCEED                   = 230.1     # v1 of code 230
GUEST_LOGGED_IN_PROCEED                 = 230.2     # v2 of code 230
REQ_FILE_ACTN_COMPLETED_OK              = 250
PWD_REPLY                               = 257

USR_NAME_OK_NEED_PASS                   = 331.1     # v1 of Code 331
GUEST_NAME_OK_NEED_EMAIL                = 331.2     # v2 of code 331
NEED_ACCT_FOR_LOGIN                     = 332
REQ_FILE_ACTN_PENDING_FURTHER_INFO      = 350

SVC_NOT_AVAIL_CLOSING_CTRL_CNX          = 421
CANT_OPEN_DATA_CNX                      = 425
CNX_CLOSED_TXFR_ABORTED                 = 426
REQ_ACTN_ABRTD_FILE_UNAVAIL             = 450
REQ_ACTN_ABRTD_LOCAL_ERR                = 451
REQ_ACTN_ABRTD_INSUFF_STORAGE           = 452

SYNTAX_ERR                              = 500
SYNTAX_ERR_IN_ARGS                      = 501
CMD_NOT_IMPLMNTD                        = 502
BAD_CMD_SEQ                             = 503
CMD_NOT_IMPLMNTD_FOR_PARAM              = 504
NOT_LOGGED_IN                           = 530.1     # v1 of code 530 - please log in
AUTH_FAILURE                            = 530.2     # v2 of code 530 - authorization failure
NEED_ACCT_FOR_STOR                      = 532
FILE_NOT_FOUND                          = 550.1     # no such file or directory
PERMISSION_DENIED                       = 550.2     # permission denied
ANON_USER_DENIED                        = 550.3     # anonymous users can't alter filesystem
IS_NOT_A_DIR                            = 550.4     # rmd called on a path that is not a directory
REQ_ACTN_NOT_TAKEN                      = 550.5
PAGE_TYPE_UNK                           = 551
EXCEEDED_STORAGE_ALLOC                  = 552
FILENAME_NOT_ALLOWED                    = 553


RESPONSES = {
    # -- 100's --
    RESTART_MARKER_REPLY:               '110 MARK yyyy-mmmm', # TODO: this must be fixed
    SERVICE_READY_IN_N_MINUTES:         '120 service ready in %s minutes',
    DATA_CNX_ALREADY_OPEN_START_XFR:    '125 Data connection already open, starting transfer',
    FILE_STATUS_OK_OPEN_DATA_CNX:       '150 File status okay; about to open data connection.',

    # -- 200's --
    CMD_OK:                             '200 Command OK',
    TYPE_SET_OK:                        '200 Type set to %s.',
    CMD_NOT_IMPLMNTD_SUPERFLUOUS:       '202 command not implemented, superfluous at this site',
    SYS_STATUS_OR_HELP_REPLY:           '211 system status reply',
    DIR_STATUS:                         '212 %s',
    FILE_STATUS:                        '213 %s',
    HELP_MSG:                           '214 help: %s',
    NAME_SYS_TYPE:                      '215 UNIX Type: L8',
    WELCOME_MSG:                        '220 Welcome, twisted.ftp at your service.',
    SVC_READY_FOR_NEW_USER:             '220 Service ready',
    GOODBYE_MSG:                        '221 Goodbye.',
    DATA_CNX_OPEN_NO_XFR_IN_PROGRESS:   '225 data connection open, no transfer in progress',
    CLOSING_DATA_CNX:                   '226 Abort successful',
    TXFR_COMPLETE_OK:                   '226 Transfer Complete.',
    ENTERING_PASV_MODE:                 '227 Entering Passive Mode',
    ENTERING_EPSV_MODE:                 '229 Entering Extended Passive Mode (|||%s|).', # where is epsv defined in the rfc's?
    USR_LOGGED_IN_PROCEED:              '230 User logged in, proceed',
    GUEST_LOGGED_IN_PROCEED:            '230 Guest login ok, access restrictions apply.',
    REQ_FILE_ACTN_COMPLETED_OK:         '250 Requested File Action Completed OK', #i.e. CWD completed ok
    PWD_REPLY:                          '257 "%s" is current directory.',

    # -- 300's --
    'userotp':                          '331 Response to %s.',  # ???
    USR_NAME_OK_NEED_PASS:              '331 Password required for %s.',
    GUEST_NAME_OK_NEED_EMAIL:           '331 Guest login ok, type your email address as password.',

    # -- 400's --
    SVC_NOT_AVAIL_CLOSING_CTRL_CNX:     '421 Service not available, closing control connection.',
    CANT_OPEN_DATA_CNX:                 "425 Can't open data connection.",
    CNX_CLOSED_TXFR_ABORTED:            '426 Transfer aborted.  Data connection closed.',

    # -- 500's --
    SYNTAX_ERR:                         "500 '%s': syntax error, command not understood.",
    SYNTAX_ERR_IN_ARGS:                 '501 syntax error in argument(s) %s.',
    CMD_NOT_IMPLMNTD:                   "502 command '%s' not implemented",
    BAD_CMD_SEQ:                        '503 Incorrect sequence of commands: %s',
    CMD_NOT_IMPLMNTD_FOR_PARAM:         "504 Not implemented for parameter '%s'.",
    NOT_LOGGED_IN:                      '530 Please login with USER and PASS.',
    AUTH_FAILURE:                       '530 Sorry, Authentication failed. %s',
    NEED_ACCT_FOR_STOR:                 '532 Need an account for storing files',
    FILE_NOT_FOUND:                     '550 %s: No such file or directory.',
    PERMISSION_DENIED:                  '550 %s: Permission denied.',
    ANON_USER_DENIED:                   '550 Anonymous users are forbidden to change the filesystem', 
    IS_NOT_A_DIR:                       '550 cannot rmd, %s is not a directory',
    REQ_ACTN_NOT_TAKEN:                 '550 requested action not taken: %s',
    EXCEEDED_STORAGE_ALLOC:             '552 requested file action aborted, exceeded file storage allocation',
    FILENAME_NOT_ALLOWED:               '553 requested action not taken, file name not allowed'
}

# -- Utility functions --

def decodeHostPort(line):
    """Decode an FTP response specifying a host and port.
    
    see RFC sec. 4.1.2 "PORT"

    @returns: a 2-tuple of (host, port).
    """
    abcdef = re.sub('[^0-9, ]', '', line[4:])
    a, b, c, d, e, f = map(str.strip, abcdef.split(','))
    host = "%s.%s.%s.%s" % (a, b, c, d)
    port = (int(e)<<8) + int(f)
    return host, port

# -- Custom Exceptions

class FileNotFoundException(Exception):
    pass

class PermissionDeniedException(Exception):
    pass

class AnonUserDeniedException(Exception):
    """raised when an anonymous user issues a command
    that will alter the filesystem
    """
    pass

class IsNotADirectoryException(Exception):
    '''raised when RMD is called on a path that isn't a directory
    '''
    pass

class OperationFailedException(Exception):
    '''raised when a command like rmd or mkdir fails for a reason other than permissions errors
    '''
    pass

class BogusSyntaxException(Exception):
    pass



class DTP(protocol.Protocol):
    pass


class DTPFactory(protocol.Factory):
    protocol = DTP
    pi = None

    def buildProtocol(self, addr):
        p = protocol.Factory.buildProtocol(self, addr)      # like in __init__ of a base-class
        p.factory = self
        return p


class FTP(basic.LineReceiver):      # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    portal  = None
    shell   = None      # the avatar
    dtp     = None      # the DTP instance this PI will use
    
    def connectionMade(self):
        self.reply(WELCOME_MSG)

    def connectionLost(self, reason):
        print "Oops! lost connection %s" % reason

    def lineReceived(self, line):
        "Process the input from the client"
        line = string.strip(line)
        if self.debug:
            log.msg(repr(line))
        command = string.split(line)
        if command == []:
            self.reply(SYNTAX_ERR, '')
            return 0
        commandTmp, command = command[0], ''
        command = commandTmp.encode('ascii', 'discard') 
        command = command.upper()
        if self.debug:
            log.msg("-"+command+"-")
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
        
        if method:
            try:
                method(params)
            except BogusSyntaxException, e:
                self.reply(SYNTAX_ERR, string.upper(command))
                return
        else:
            self.reply(CMD_NOT_IMPLMNTD, string.upper(command))

    def reply(self, key, s = ''):
        if string.find(RESPONSES[key], '%s') > -1:
            if self.debug:
                log.msg(RESPONSES[key] % s + '\r\n')
            self.transport.write(RESPONSES[key] % s + '\r\n')
        else:
            if self.debug:
                log.msg(RESPONSES[key] + '\r\n')
            self.transport.write(RESPONSES[key] + '\r\n')
#        return self.shell != None   # Why is this here ???

    def createPassiveDTP(self):
        self.dtp = self.dtpFactory.buildProtocol()

    def ftp_LIST(self, params):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        sioObj = self.shell.list(params)    # returns a StringIO object
        size = len(sioObj.getvalue())     # filesize == length of string value
        self.queuedFile = QueuedFile(sioObj, size) 
        self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self.setAction('LIST')
 
    def ftp_PWD(self, params):
        """ Print working directory command
        """
        # TODO: should print the TLD-RELATIVE working directory
        self.reply(PWD_REPLY, self.shell.pwd())


    def ftp_PASV(self, params):
        """Request for a passive connection

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
        # if we don't have an avatar for this command 
        if not self.shell:      
            self.reply(NOT_LOGGED_IN)
            return

        #self.createPassiveServer()
        # Use the ip from the pi-connection
        sockname = self.transport.getHost()
        localip = string.replace(sockname[1], '.', ',')
        lport = self.dtpPort.socket.getsockname()[1]

        # what's with the / 256 ?
        lp1 = lport / 256                           
        lp2, lp1 = str(lport - lp1*256), str(lp1)

        # TODO: replace with RESPONSE code
        self.transport.write('227 Entering Passive Mode ('+localip+
                             ','+lp1+','+lp2+')\r\n')



class FTPFactory(protocol.Factory):
    protocol = FTP

    def __init__(self, portal=None):
        self.portal = portal
        import warnings
        warnings.warn("The FTP server is INSECURE, please don't run it on the internet")

    def buildProtocol(self, addr):
        pi = protocol.Factory.buildProtocol(self, addr)
        pi.protocol = self.protocol
        pi.portal = self.portal
        pi.dtpFactory = DTPFactory
        pi.dtpFactory.pi = pi
        return pi

   
class IFTPShell(components.Interface):
    """An abstraction of the shell commands used by the FTP protocol
    for a given user account
    """

    def buildFullPath(self, path):
        """converts a specified path relative to the user's top level directory
        into a path in the filesystem representation

        example: if the user's tld is /home/foo and there's a file in the filesystem
        /home/foo/bar/spam.tar.gz the user would specify path /bar/spam.tar.gz in the 
        ftp command, and this function would translate it into /home/foo/bar/spam.tar.gz
        """
        pass

    def pwd(self):
        """ Print working directory command
        """
        pass

    def cwd(self, path):
        """Change working directory

        should throw a FileNotFound exception on failure

        from the rfc:
            This command allows the user to work with a different
            directory or dataset for file storage or retrieval without
            altering his login or accounting information.  Transfer
            parameters are similarly unchanged.  The argument is a
            pathname specifying a directory or other system dependent
            file group designator.
        """
        pass

    def cdup(self):
        '''changes to the parent of the current working directory
        '''
        pass

    def size(self, path):
        '''returns the size of the file specified by path in bytes
        '''
        pass

    def mkd(self, path):
        """ This command causes the directory specified in the pathname
        to be created as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative).
        """
        pass

    def rmd(self, path):
        """ This command causes the directory specified in the pathname
        to be removed as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative). 
        """
        pass

    def dele(self, path):
        """ This command causes the file specified in the pathname to be
        deleted at the server site. 
        """
        pass

    def list(self, path):
        """return a StringIO object containing the directory listing to
        be sent to the client via the DTP

        from the rfc:
            This command causes a list to be sent from the server to the
            passive DTP.  If the pathname specifies a directory or other
            group of files, the server should transfer a list of files
            in the specified directory.  If the pathname specifies a
            file then the server should send current information on the
            file.  A null argument implies the user's current working or
            default directory.
        """
        pass

    def nlst(self, path):
        """This command causes a directory listing to be sent from
        server to user site.  The pathname should specify a
        directory or other system-specific file group descriptor; a
        null argument implies the current directory. This command is intended
        to return information that can be used by a program to
        further process the files automatically.  For example, in
        the implementation of a "multiple get" function.
        """
        pass

    def retr(self, path):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.
        """
        pass

    def stor(self, params):
        """This command causes the server-DTP to accept the data
        transferred via the data connection and to store the data as
        a file at the server site.  If the file specified in the
        pathname exists at the server site, then its contents shall
        be replaced by the data being transferred.  A new file is
        created at the server site if the file specified in the
        pathname does not already exist.
        """
        pass

class FTPAnonymousShell(object):
    __implements__ = (IFTPShell,)
    wd   = None     # working directory
    tld  = None     # top level directory
    user = None     # user name

    def buildFullPath(self, rpath):
        """Build a new path, from a relative path based on the current wd
        This routine is not fully tested, and I fear that it can be
        exploited by building clever paths
        """
        npath = os.path.normpath(rpath)
#        if npath == '':
#            npath = '/'
        if not os.path.isabs(npath):
            npath = os.path.normpath(self.wd + '/' + npath)
#        npath = self.tld + npath
        return os.path.normpath(npath) # finalize path appending 

    def pwd(self):
        return self.wd

    def cwd(self, path):
        wd = os.path.normpath(path)
        if not os.path.isabs(wd):
            wd = os.path.normpath(self.wd + '/' + wd)
        wd = string.replace(wd, '\\','/')
        while string.find(wd, '//') > -1:
            wd = string.replace(wd, '//','/')
        # '..', '\\', and '//' is there just to prevent stop hacking :P
        if (not os.path.isdir(self.tld + wd)) or (string.find(wd, '..') > 0) or \
            (string.find(wd, '\\') > 0) or (string.find(wd, '//') > 0): 
            # TODO: test this exception
            raise FileNotFoundException(path)
        else:
            wd = string.replace(wd, '\\','/')
            self.wd = wd

    def cdup(self):
        self.cwd('..')

    def size(self, path):
        # is this specified in the RFC?
        """"""
        npath = self.buildFullPath(path)
        if not os.path.isfile(npath):
            raise FileNotFoundException(path)
        return os.path.getsize(npath)

    def dele(self, path):
        raise AnonUserDeniedException()
        
    def mkd(self, path):
        raise AnonUserDeniedException()
        
    def rmd(self, path):
        raise AnonUserDeniedException()
 
    def retr(self, path):
        npath = self.buildFullPath(path)
        if not os.path.isfile(npath):
            raise FileNotFoundException(npath)
        if not os.access(npath, os.O_RDONLY):
            raise PermissionDeniedException(npath)
        return npath

    def stor(self, params):
        raise AnonUserDeniedException()

    def list(self, path):
        alist = os.listdir(self.buildFullPath(path))
        s = ''
        for a in alist:
            ts = a
            ff = os.path.join(path, ts) # the full filename
            try:
                # os.path.getmtime calls os.stat: os.stat fails w/ an IOError
                # on broken symlinks.  I know there's some way to get the real
                # mtime out, since ls does it, but I haven't had time to figure
                # out how to do it from python.
                mtn = os.path.getmtime(ff)
                fsize = os.path.getsize(ff)
            except OSError:
                mtn = 0
                fsize = 0
            mtime = time.strftime("%b %d %H:%M", time.gmtime(mtn))
            if os.path.isdir(ff):
                diracc = 'd'
            else:
                diracc = '-'    
            s = s + diracc+"r-xr-xr-x    1 twisted twisted %11d" % fsize+' '+mtime+' '+ts+'\r\n'

        return StringIO(s)

    def nlist(self, path):
        pass


#from newftp import FTP, FTPFactory, IFTPShell, FTPAnonymousShell


class FTPRealm:
    __implements__ = (portal.IRealm,)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IFTPShell in interfaces:
            if avatarId == checkers.ANONYMOUS:
                avatar = FTPAnonymousShell()
                avatar.tld = os.path.abspath(".")
                avatar.wd = avatar.tld
                avatar.user = 'anonymous'
                avatar.logout = None
            return IFTPShell, avatar, avatar.logout
        raise NotImplementedError("Only IFTPShell interface is supported by this realm")


def main():
    # Construct the application
    application = service.Application("ftpserver")

    # Get the IServiceCollection interface
    myService = service.IServiceCollection(application)

    # Create the protocol factory
    ftpFactory = FTPFactory()
    p = portal.Portal(FTPRealm())
    p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

    ftpFactory.portal = p
    ftpFactory.root = '/home/jonathan'
    ftpFactory.protocol = FTP

    from twisted.internet import reactor
    reactor.listenTCP(2121, ftpFactory)
    reactor.run


if __name__ == "__main__":
   main() 




