# originally written by phed 
# FTPClient written by spiv
# server and client refactor by slyphon (Jonathan D. Simms)

# System Imports
import os
import time
import string
import types
import re
from cStringIO import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application
from twisted import internet
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log, components

from twisted.cred import error, portal, checkers, credentials

#-------------------------------------------------------------------------------
# TODO:
#
# ADD:     Need to make DTPCommand return a deferred so if client hasn't connectd
#          their DTP, the command will just wait to execute
#
# TEST:    when client-PI connects and opens DTP then client-PI quits 
#          make sure DTP connection quits and closes and cannot be
#          reconnected to
#
# Ask:     How do i handle errors so that the whole server doesn't crash on
#          exception?
#
#-------------------------------------------------------------------------------

# constants

MODULE_DEBUG = True

PASV = 1
ACTV = 2

ENDLN = str('\015\012')

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


RESPONSE = {
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
    ENTERING_PASV_MODE:                 '227 =%s',
    ENTERING_EPSV_MODE:                 '229 Entering Extended Passive Mode (|||%s|).', # where is epsv defined in the rfc's?
    USR_LOGGED_IN_PROCEED:              '230 User logged in, proceed',
    GUEST_LOGGED_IN_PROCEED:            '230 Anonymous login ok, access restrictions apply.',
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

# -- Utility Functions --

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

def debugDeferred(self, *_):
    log.debug(_)
        
# -- Custom Exceptions --

class FileNotFoundError(Exception):
    pass

class PermissionDeniedError(Exception):
    pass

class AnonUserDeniedError(Exception):
    """raised when an anonymous user issues a command
    that will alter the filesystem
    """
    pass

class IsNotADirectoryError(Exception):
    '''raised when RMD is called on a path that isn't a directory
    '''
    pass

class OperationFailedError(Exception):
    '''raised when a command like rmd or mkdir fails for a reason other than permissions errors
    '''
    pass

class BogusSyntaxError(Exception):
    pass

class FTPError(Exception):
    pass

class DTPError(Exception):
    pass

class DTPFactoryBogusHostError(Exception):
    '''thrown when a host other than the one we opened this 
    DTP connection for attempts to connect'''
    pass

class PathBelowTLDError(Exception):
    pass

class ClientDisconnectError(Exception):
    pass

# ------------------

# -- DTP Protocol --

def _getFPName(fp):
    '''returns a file object's name attr if it has one,
    otherwise it returns "name"
    '''
    if hasattr(fp, 'name'):
        return fp.name
    return 'file'   # stringIO objects have no .name attr

# moshez's wonderful contribution! 
#class PortTracker:
#    def __init__(self, factory):
#        self.factory = factory
#        self.ports = ports
#    def listenOn(self, s):
#        self.ports.append(strports.listen(s, self.factory))
#    def stopListening(self, s):
#        for port in self.ports: port.stopListening()



class DTP(protocol.Protocol, basic.FileSender):
    fp = None

    def connectionMade(self):
        """Will start an transfer, if one is queued up, 
        when the client connects"""
        peer = self.transport.getPeer()
        log.debug('got a DTP connection %s:%s' % (peer[1],peer[2]))

        if self.factory.peerCheck and peer[1] != self.factory.pi.peerHost[1]:
            # DANGER Will Robinson! Bailing!
            log.debug('dtp ip did not match ftp ip')
            self.cleanup()      

        d, self.factory.deferred = self.factory.deferred, defer.Deferred()
        log.debug('firing dtpFactory deferred')
        d.callback(None)

    def connectionLost(self, reason):
        log.msg('lost DTP connection %s, oh well!' % reason)
        self.factory.stopFactory()

    def dtp_RETR(self, fp): # RETR = sendFile
        '''ssnds a file object out the wire'''
        filename = _getFPName(fp)
        self.fp = fp

        log.debug('sendfile sending %s' % filename)
        return self.beginFileTransfer(self.fp, self.transport) 


class PasvDTPFactory(protocol.ServerFactory):
    # -- configuration variables --
    peerCheck = True

    # -- class variables --
    protocol = DTP
    pi = None
    peerHost = None
    instance = None
    deferred = defer.Deferred()     # deferred will fire when instance is connected to

    def buildProtocol(self, addr):
        if self.instance:   # only create one instance
            return 
        p = protocol.ServerFactory.buildProtocol(self, addr)      # like in __init__ of a base-class
        p.factory = self
        p.pi = self.pi
        self.pi.dtpInstance = p
        return p

    def stopFactory(self):
        self.pi.cleanupDTP()



# -- FTP-PI (Protocol Interpreter) --


def cleanPath(params):
    # cleanup backslashes and multiple foreslashes
    if params:
        params = re.sub(r'[\\]{2,}?', '/', params)
        params = re.sub(r'[/]{2,}?','/', params)
    return params

class FTP(basic.LineReceiver):      
    # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    portal      = None
    shell       = None      # the avatar
    dtpFactory  = None      # generates a single DTP for this session
    dtpInstance = None      # a DTP protocol instance
    dtpPort     = None      # the port that the DTPFactory is listening on
    user        = None      # the username of the client connected 
    peerHost    = None      # the (type,ip,port) of the client
    dtpTxfrMode = ACTV      # PASV or ACTV, default ACTV
    blocked     = None      # a command queue for pipelining 

    
    def connectionMade(self):
        log.debug('ftp-pi connectionMade')
        self.reply(WELCOME_MSG)
        self.peerHost = self.transport.getPeer()
        self.__testingautologin()

    def __testingautologin(self):
        import warnings; warnings.warn('''

            --> DEBUGGING CODE ACTIVE!!! <--
''')
        lr = self.lineReceived
        lr('USER anonymous')
        lr('PASS f@d.com')
        lr('PASV')
        lr('LIST')
        lr('RETR .vim/vimrc')
        lr('RETR Session.vim')


    def connectionLost(self, reason):
        log.msg("Oops! lost connection\n %s" % reason)
        # if we have a DTP protocol instance running and
        # we lose connection to the client's PI, kill the 
        # DTP connection and close the port
        if hasattr(self.dtpFactory, 'instance') and self.dtpFactory.instance:
            self.dtpFactory.instance.cleanup()
            self.dtpFactory

    def lineReceived(self, line):
        "Process the input from the client"
        line = string.strip(line)
        log.debug(repr(line))
        line = line.encode('ascii', 'discard') 
        try:
            return self.processCommand(*line.split())
        except BogusSyntaxError, e:
            self.reply(SYNTAX_ERR, string.upper(command))
        except FTPError, e:
            log.err(e)
            self.reply(CMD_NOT_IMPLMNTD, e.args[0])
        except (ValueError, AttributeError, TypeError), e:
            log.err(e)

    # TODO: all DTP commands to be processed here !!!
    def processCommand(self, cmd, *args):
        if self.blocked != None:
            log.debug('FTP is queueing command: %s' % cmd)
            self.blocked.append((cmd,args))
            return

        cmd = cmd.upper()
        if cmd not in ['USER','PASS'] and not self.shell:
            log.debug('ftp_%s returning, user not logged in' % cmd)
            self.reply(NOT_LOGGED_IN)
            return

        if cmd in ['RETR', 'STOR', 'LIST', 'PORT']:             # if this is a DTP related command
            if not self.dtpInstance:                            # if no one has connected yet
                # a bit hackish, but manually blocks this command 
                # until we've set up the DTP protocol instance
                assert self.blocked == None
                self.blocked = [(cmd,args)]   
                log.debug('during dtp setup, blocked = %s' % self.blocked)
                return
        method = getattr(self, "ftp_%s" % cmd, None)      
        if method:
            return method(*args)
        log.debug("SOMETHING IS SCREWY")


    def _unblock(self, *_):
        log.debug('_unblock running')
        commands = self.blocked
        self.blocked = None
        while commands and self.blocked is None:
            cmd, args = commands.pop(0)
            self.processCommand(cmd, *args)
        if self.blocked is not None:
            self.blocked.extend(commands)

    def _ebDtpInstance(self, _):
        # TODO: add cleanup here if a bogus connection happens or
        #       if the client disconnects before downloading everything
        log.debug(_)

    def reply(self, key, s = ''):
        if string.find(RESPONSE[key], '%s') > -1:
            log.debug(RESPONSE[key] % s + ENDLN)
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
            log.debug(RESPONSE[key] + ENDLN)
            self.transport.write(RESPONSE[key] + ENDLN)

    def _createActiveDTP(self):
        log.debug('_createActiveDTP')
        raise NotImplementedError()

    def _createPassiveDTP(self):
        """sets up a DTPFactory listening on an ephemeral port
        port is stored in self.dtpPort
        @returns a deferred that will be fired when a connection is made
        """
        log.debug('_createPassiveDTP')
        # TODO: figure out what happens if there's an existing ACTV 
        #       DTP connection and the client calls PASV
        self.dtpTxfrMode = PASV     # ensure state is correct
        if not self.dtpFactory:
            self.dtpFactory = PasvDTPFactory()
            self.dtpFactory.pi = self
            self.dtpFactory.peerHost = self.transport.getPeer()[1]
            self.dtpPort = reactor.listenTCP(0, self.dtpFactory)   
            return self.dtpFactory.deferred

    def _createDTP(self):
        log.debug('_createDTP')
        if self.dtpTxfrMode != ACTV:
            d = self._createPassiveDTP()
        else: 
            d = self._createActiveDTP()

        d = self.dtpFactory.deferred        
        d.addCallback(debugDeferred, 'dtpFactory deferred')
        d.addCallback(self._unblock)                     # call _unblock when client connects
        d.addErrback(self._ebDtpInstance)

    def cleanupDTP(self):
        """called when DTP connection exits"""
        log.debug('cleanupDTP')

        if hasattr(self.dtpPort, 'connected'):
            self.dtpPort.loseConnection()
            self.dtpPort.stopListening()
            self.dtpFactory = None
            self.dtpInstance = None
            self.dtpPort = None

    def _doDTPCommand(self, cmd, arg):
        if self.blocked is None:
            self.blocked = []
        try:
            f = getattr(self.dtpInstance, "dtp_%s" % cmd, None)
        except AttributeError, e:
            log.err('SOMETHING IS SCREWY IN _doDTPCommand')
            raise e

        defer.maybeDeferred(f, arg
                ).addCallback(self._cbDTPCommand
                ).addCallback(self._unblock
                ).addErrback(self._ebDTPCommand)

    def _cbDTPCommand(self, arg):
        log.debug("DTP Command success: %s" % arg)
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def _ebDTPCommand(self, arg):
        log.err("DTP Command failed: %s" % str(arg))
        arg.printTraceback()

    def ftp_USER(self, params):
        """Get the login name, and reset the session
        PASS is expected to follow

        from the rfc:
            The argument field is a Telnet string identifying the user.
            The user identification is that which is required by the
            server for access to its file system.  This command will
            normally be the first command transmitted by the user after
            the control connections are made

            This has the effect of flushing any user, password, and account
            information already supplied and beginning the login sequence
            again.  All transfer parameters are unchanged and any file transfer
            in progress is completed under the old access control parameters.
        """
        if params=='':
            raise BogusSyntaxError('no parameters')
        self.user = string.split(params)[0]
        log.debug('ftp_USER params: %s' % params)
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)
        self.type = 'A'

    def ftp_PASS(self, params):
        """Authorize the USER and the submitted password

        from the rfc:
            The argument field is a Telnet string specifying the user's
            password.  This command must be immediately preceded by the
            user name command, and, for some sites, completes the user's
            identification for access control.
        """

        # the difference between an Anon login and a User login is 
        # the avatar that will be returned to the callback
        if not self.user:
            self.reply(BAD_CMD_SEQ, 'USER required before PASS')
            return

        log.debug('ftp_PASS params: %s' % params)

        # parse password
        self.passwd = params.split()[0] 

        # if this is an anonymous login
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        IFTPShell
                    ).addCallbacks(self._cbAnonLogin, self._ebLogin
                    )
            else:
                # if cred has been set up correctly, this shouldn't happen
                self.reply(AUTH_FAILURE, 'internal server error')

        # otherwise this is a user login
        else:
            if self.portal:
                self.portal.login(
                        credentials.UsernamePassword(self.user, self.passwd),
                        None,
                        IFTPShell
                    ).addCallbacks(self._cbLogin, self.ebLogin
                    )
            else:
                self.reply(AUTH_FAILURE, 'internal server error')

    def _cbAnonLogin(self, (interface, avatar, logout)):
        '''anonymous login'''
        assert interface is IFTPShell
        peer = self.transport.getPeer()
#       log.debug("Anonymous login from %s:%s" % (peer[1], peer[2]))
        self.shell = avatar
        self.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        '''authorized user login'''
        assert interface is IFTPShell
        self.shell = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure):
        failure.trap(error.UnauthorizedLogin)
        self.reply(AUTH_FAILURE, '')

    def ftp_LIST(self, params=''):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
        log.debug('ftp_LIST: %s' % params)
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        sioObj = self.shell.list(cleanPath(params))    # returns a StringIO object
        self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        self._doDTPCommand('RETR', sioObj)
 
    def ftp_PWD(self, params):
        """ Print working directory command
        """
        # TODO: should print the TLD-RELATIVE working directory
        self.reply(PWD_REPLY, self.shell.pwd())

    def ftp_PASV(self, *_):
        """Request for a passive connection

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
        log.debug('ftp_PASV') 
        self.dtpTxfrMode = PASV
        if not self.dtpFactory:                             # if we haven't set up a DTP port yet
            try:
                self._createDTP()
            except OSError, e:
                log.msg("CRITICAL BUG!! THIS SHOULD NOT HAVE HAPPENED!!! %s" % e)
        sockname = self.transport.getHost()             # Use the ip from the PI-connection
        localip = string.replace(sockname[1], '.', ',')
        lport = self.dtpPort.socket.getsockname()[1]
        lp1 = lport / 256                               # convert port into two 8-byte values
        lp2, lp1 = str(lport - lp1*256), str(lp1)
        self.reply(ENTERING_PASV_MODE, "%s,%s,%s" % (localip, lp1, lp2))
        log.debug("passive port open on: %s:%s" % (localip, lport), level="debug")

    def ftp_CWD(self, params):
        try:
            self.shell.cwd(cleanPath(params))
        except FileNotFoundError, e:
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, e:
            self.reply(PERMISSION_DENIED, e)
        else:
            self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_CDUP(self, params):
        try:
            self.shell.cdup()
        except FileNotFoundError, e:
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, e:
            self.reply(PERMISSION_DENIED, e)
        else:
            self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_RETR(self, param):
        try:
            fp = self.shell.retr(cleanPath(param))
            self._doDTPCommand('RETR', fp)
        except FileNotFoundError, e:
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, e:
            self.reply(PERMISSION_DENIED, e)
        else:

        # the dtp will take care of sending REQ_FILE_ACTN_COMPLETED_OK 
        # when it has completed the transfer

class FTPFactory(protocol.Factory):
    protocol = FTP
    allowAnonymous = True
    userAnonymous = 'anonymous'
    
    def __init__(self, portal=None):
        self.portal = portal

    def buildProtocol(self, addr):
        pi = protocol.Factory.buildProtocol(self, addr)
        pi.protocol = self.protocol
        pi.portal = self.portal
        return pi

# -- Cred Objects --

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

        returns an opened file-like object to the data requested
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

    user     = None         # user name
    clientwd = None
    tld      = None
    debug    = True

    # basically, i'm thinking of the paths as a list of path elements
    #
    # some terminology:
    # client absolute path = an absolute path minus the tld
    # server absolute path = a full absolute path on the filesystem
    # client relative path = a path relative to the client's working directory

    def pwd(self):
        return self.clientwd

    def myjoin(self, lpath, rpath):
        if lpath and lpath[-1] == os.sep:
            lpath = lpath[:-1]
        if rpath and rpath[0] == os.sep:
            rpath = rpath[1:]
        return "%s/%s" % (lpath, rpath)

    def mapCPathToSPath(self, rpath):
        if not rpath or rpath[0] != '/':      # if this is not an absolute path
            # add the clients working directory to the requested path
            mappedClientPath = self.myjoin(self.clientwd, rpath) 
        # next add the client's top level directory to the requested path
        mappedServerPath = self.myjoin(self.tld, mappedClientPath)
        ncpath, nspath = os.path.normpath(mappedClientPath), os.path.normpath(mappedServerPath)
        common = os.path.commonprefix([self.tld, nspath])
        if common != self.tld:
            raise PathBelowTLDError('Cannot access below / directory')
        class _:
            def __init__(self, cpath, spath):
                self.clientPath = cpath
                self.serverPath = spath
        return _(ncpath, nspath)

 
    def cwd(self, path):
        mapped = self.mapCPathToSPath(path)
        if os.path.exists(mapped.clientPath) and os.path.isdir(mapped.serverPath):
            self.clientwd = mapped.clientPath
        else:
            raise FileNotFoundError(mapped.clientPath)
       
    def cdup(self):
        self.cwd('..')

#    def size(self, path):
#        # is this specified in the RFC?
#        """"""
#        npath = self.buildFullPath(path)
#        if not os.path.isfile(npath):
#            raise FileNotFoundError(path)
#        return os.path.getsize(npath)

    def dele(self, path):
        raise AnonUserDeniedError()
        
    def mkd(self, path):
        raise AnonUserDeniedError()
        
    def rmd(self, path):
        raise AnonUserDeniedError()
 
    def retr(self, path):
        mapped = self.mapCPathToSPath(path)
        if not os.path.isfile(mapped.serverPath):
            raise FileNotFoundError(mapped.clientPath)
#        if not os.access(npath, os.O_RDONLY):
#            raise PermissionDeniedError(npath)
        # TODO: need to do some kind of permissions checking here
        return file(mapped.serverPath, 'rb')

    def stor(self, params):
        raise AnonUserDeniedError()

    def list(self, path):
        spath = self.mapCPathToSPath(path).serverPath
        alist = os.listdir(spath)
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
        sio = StringIO(s)
        sio.seek(0)         # rewind the file position to the beginning
        return sio

    def nlist(self, path):
        pass


class FTPRealm:
    __implements__ = (portal.IRealm,)
    ANONYMOUS_DIR = '/home/jonathan'

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IFTPShell in interfaces:
            if avatarId == checkers.ANONYMOUS:
                avatar = FTPAnonymousShell()
                avatar.tld = self.ANONYMOUS_DIR
                avatar.clientwd = '/'
                avatar.user = 'anonymous'
                avatar.logout = None
            return IFTPShell, avatar, avatar.logout
        raise NotImplementedError("Only IFTPShell interface is supported by this realm")




