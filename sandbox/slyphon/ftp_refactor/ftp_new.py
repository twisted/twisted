# -*- test-case-name: twisted.test.test_ftp -*-
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

"""
An FTP protocol implementation

Maintainer: U{Jonathan D. Simms<mailto:slyphon@twistedmatrix.com>}

"""

# System Imports
import os
import time
import string
import types
import re
from cStringIO import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error, defer
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic, policies
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application, internet, python
from twisted.python import failure, log, components

from twisted.cred import error as cred_error, portal, checkers, credentials


# transfer modes
PASV, PORT = 1, 2

ENDLN = str('\015\012')

# response codes

RESTART_MARKER_REPLY                    = "100"
SERVICE_READY_IN_N_MINUTES              = "120"
DATA_CNX_ALREADY_OPEN_START_XFR         = "125"
FILE_STATUS_OK_OPEN_DATA_CNX            = "150"

CMD_OK                                  = "200.1"
TYPE_SET_OK                             = "200.2"
ENTERING_PORT_MODE                      = "200.3"
CMD_NOT_IMPLMNTD_SUPERFLUOUS            = "202"
SYS_STATUS_OR_HELP_REPLY                = "211"
DIR_STATUS                              = "212"
FILE_STATUS                             = "213"
HELP_MSG                                = "214"
NAME_SYS_TYPE                           = "215"
SVC_READY_FOR_NEW_USER                  = "220.1"
WELCOME_MSG                             = "220.2"
SVC_CLOSING_CTRL_CNX                    = "221"
GOODBYE_MSG                             = "221"
DATA_CNX_OPEN_NO_XFR_IN_PROGRESS        = "225"
CLOSING_DATA_CNX                        = "226"
TXFR_COMPLETE_OK                        = "226"
ENTERING_PASV_MODE                      = "227"
ENTERING_EPSV_MODE                      = "229"
USR_LOGGED_IN_PROCEED                   = "230.1"     # v1 of code 230
GUEST_LOGGED_IN_PROCEED                 = "230.2"     # v2 of code 230
REQ_FILE_ACTN_COMPLETED_OK              = "250"
PWD_REPLY                               = "257"

USR_NAME_OK_NEED_PASS                   = "331.1"     # v1 of Code 331
GUEST_NAME_OK_NEED_EMAIL                = "331.2"     # v2 of code 331
NEED_ACCT_FOR_LOGIN                     = "332"
REQ_FILE_ACTN_PENDING_FURTHER_INFO      = "350"

SVC_NOT_AVAIL_CLOSING_CTRL_CNX          = "421.1"
TOO_MANY_CONNECTIONS                    = "421.2"
CANT_OPEN_DATA_CNX                      = "425"
CNX_CLOSED_TXFR_ABORTED                 = "426"
REQ_ACTN_ABRTD_FILE_UNAVAIL             = "450"
REQ_ACTN_ABRTD_LOCAL_ERR                = "451"
REQ_ACTN_ABRTD_INSUFF_STORAGE           = "452"

SYNTAX_ERR                              = "500"
SYNTAX_ERR_IN_ARGS                      = "501"
CMD_NOT_IMPLMNTD                        = "502"
BAD_CMD_SEQ                             = "503"
CMD_NOT_IMPLMNTD_FOR_PARAM              = "504"
NOT_LOGGED_IN                           = "530.1"     # v1 of code 530 - please log in
AUTH_FAILURE                            = "530.2"     # v2 of code 530 - authorization failure
NEED_ACCT_FOR_STOR                      = "532"
FILE_NOT_FOUND                          = "550.1"     # no such file or directory
PERMISSION_DENIED                       = "550.2"     # permission denied
ANON_USER_DENIED                        = "550.3"     # anonymous users can't alter filesystem
IS_NOT_A_DIR                            = "550.4"     # rmd called on a path that is not a directory
REQ_ACTN_NOT_TAKEN                      = "550.5"
PAGE_TYPE_UNK                           = "551"
EXCEEDED_STORAGE_ALLOC                  = "552"
FILENAME_NOT_ALLOWED                    = "553"


RESPONSE = {
    # -- 100's --
    RESTART_MARKER_REPLY:               '110 MARK yyyy-mmmm', # TODO: this must be fixed
    SERVICE_READY_IN_N_MINUTES:         '120 service ready in %s minutes',
    DATA_CNX_ALREADY_OPEN_START_XFR:    '125 Data connection already open, starting transfer',
    FILE_STATUS_OK_OPEN_DATA_CNX:       '150 File status okay; about to open data connection.',

    # -- 200's --
    CMD_OK:                             '200 Command OK',
    TYPE_SET_OK:                        '200 Type set to %s.',
    ENTERING_PORT_MODE:                 '200 PORT OK',
    CMD_NOT_IMPLMNTD_SUPERFLUOUS:       '202 command not implemented, superfluous at this site',
    SYS_STATUS_OR_HELP_REPLY:           '211 system status reply',
    DIR_STATUS:                         '212 %s',
    FILE_STATUS:                        '213 %s',
    HELP_MSG:                           '214 help: %s',
    NAME_SYS_TYPE:                      '215 UNIX Type: L8',
    WELCOME_MSG:                        "220-Welcome, ask your doctor if twistedmatrix.com is right for you!\r\n220 Features p .",
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
    TOO_MANY_CONNECTIONS:               '421 Too many users right now, try again in a few minutes.',
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

   
        
# -- Custom Exceptions --
class TLDNotSetInRealmError(Exception):
    '''raised if the tld (root) directory for the Realm was not set 
    before requestAvatar was called'''
    pass

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
    """raised when RMD is called on a path that isn't a directory
    """
    pass

class OperationFailedError(Exception):
    """raised when a command like rmd or mkdir fails for a reason other than permissions errors
    """
    pass

class CmdSyntaxError(Exception):
    pass

class CmdArgSyntaxError(Exception):
    pass

class CmdNotImplementedError(Exception):
    """raised when an unimplemented command is given to the server
    """
    pass

class CmdNotImplementedForArgError(Exception):
    pass

class FTPError(Exception):
    pass

class FTPTimeoutError(Exception):
    pass

class DTPError(Exception):
    pass

class BogusClientError(Exception):
    """thrown when a client other than the one we opened this 
    DTP connection for attempts to connect, or a client attempts to
    get us to connect to an ip that differs from the one where the 
    request came from"""
    pass

class PathBelowTLDError(Exception):
    pass

class ClientDisconnectError(Exception):
    pass

class BadCmdSequenceError(Exception):
    """raised when a client sends a series of commands in an illogical sequence"""
    pass

class AuthorizationError(Exception):
    """raised when client authentication fails"""
    pass

class FTP(object, basic.LineReceiver, policies.TimeoutMixin):      
    """Protocol Interpreter for the File Transfer Protocol
    
    @ivar shell: The connected avatar
    @ivar user: The username of the connected client
    @ivar peerHost: The (type, ip, port) of the client
    @ivar dtpTxfrMode: The current mode -- PASV or PORT
    @ivar blocked: Command queue for command pipelining
    @ivar binary: The transfer mode.  If false, ASCII.
    @ivar dtpFactory: Generates a single DTP for this session
    @ivar dtpPort: Port returned from listenTCP
    @ivar dtpInetPort: dtpPort.getHost()
    @ivar dtpHostPort: cluient (address, port) to connect to on a PORT command
    """
    __implements__ = IProtocol,
    # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    blockingCommands = ['RETR', 'STOR', 'LIST', 'PORT']
    reTelnetChars = re.compile(r'(\\x[0-9a-f]{2}){1,}')

    # how long the DTP waits for a connection (in seconds)
    dtpTimeout = 10

    # if this instance is the upper limit of instances allowed, then 
    # reply with appropriate error message and drop the connection
    _instanceNum = 0

    portal      = None
    shell       = None     # the avatar
    user        = None     # the username of the client connected
    peerHost    = None     # the (type,ip,port) of the client
    dtpTxfrMode = None     # PASV or PORT, no default
    blocked     = None     # a command queue for pipelining
    dtpFactory  = None     # generates a single DTP for this session
    dtpInstance = None     # a DTP protocol instance
    dtpPort     = None     # object returned from listenTCP
    dtpInetPort = None     # result of dtpPort.getHost() used for saving inet port number
    dtpHostPort = None     # client address/port to connect to on PORT command

    binary      = True     # binary transfers? False implies ASCII. defaults to True


    def connectionMade(self):
        log.debug('ftp-pi connectionMade: instance %s' % self._instanceNum)

        if (self.factory.maxProtocolInstances is not None and 
                self._instanceNum >= self.factory._maxProtocolInstances): 
            self.reply(TOO_MANY_CONNECTIONS)
            self.transport.loseConnection()
            return
        self.reply(WELCOME_MSG)                     
        self.peerHost = self.transport.getPeer()
        self.setTimeout(self.timeOut)


    def connectionLost(self, reason):
        log.msg("Oops! lost connection\n %s" % reason)
        # if we have a DTP protocol instance running and
        # we lose connection to the client's PI, kill the 
        # DTP connection and close the port
        if self.dtpFactory:
            self.cleanupDTP()
        self.setTimeout(None)

        self.factory._currentInstanceNum -= 1
        # moshez crackful optimization
        # checks for self.shell.logout and if it exists
        # calls it
        getattr(self.shell, 'logout', lambda: None)()

            
    def timeoutConnection(self):
        log.msg('FTP timed out')
        self.transport.loseConnection()

    def setTimeout(self, seconds):
#        log.msg('ftp.setTimeout to %s seconds' % str(seconds))
        policies.TimeoutMixin.setTimeout(self, seconds)

    def reply(self, key, s=''):                                               
        """format a RESPONSE and send it out over the wire"""
        if string.find(RESPONSE[key], '%s') > -1:
#            log.debug(RESPONSE[key] % s + ENDLN)
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
#            log.debug(RESPONSE[key] + ENDLN)
            self.transport.write(RESPONSE[key] + ENDLN)

    def lineReceived(self, line):
        "Process the input from the client"
        self.resetTimeout()
        line = string.strip(line)
#        log.debug(repr(line))
        line = self.reTelnetChars.sub('', line)  # clean up '\xff\xf4\xff' nonsense
        line = line.encode() 
        try:
            cmdAndArgs = line.split(' ',1)
#            log.debug('processing command %s' % cmdAndArgs)
            self.processCommand(*cmdAndArgs)
        except CmdSyntaxError, (e,):
            self.reply(SYNTAX_ERR, string.upper(command))
        except CmdArgSyntaxError, (e,):
            log.debug(e)
            self.reply(SYNTAX_ERR_IN_ARGS, e)
        except AnonUserDeniedError, (e,):
            log.debug(e)
            self.reply(ANON_USER_DENIED, e)
        except CmdNotImplementedError, (e,):
            log.debug(e)
            self.reply(CMD_NOT_IMPLMNTD, e)
        except BadCmdSequenceError, (e,): 
            log.debug(e)
            self.reply(BAD_CMD_SEQ, e)
        except AuthorizationError, (e,):
            log.debug(e)
            self.reply(AUTH_FAILURE, 'internal server error')
        except FileNotFoundError, (e,):
            log.debug(e)
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, (e,):
            log.debug(e)
            self.reply(PERMISSION_DENIED, e)
        except OperationFailedError, (e,):
            log.debug(e)
            self.reply(REQ_ACTN_NOT_TAKEN, '')
        except Exception, e:
            log.err(e)
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
            raise

    def processCommand(self, cmd, *args):
#        log.debug('FTP.processCommand: cmd = %s, args = %s' % (cmd,args))
        if self.blocked != None:                                                # all DTP commands block, 
#            log.debug('FTP is queueing command: %s' % cmd)
            self.blocked.append((cmd,args))                                     # so queue new requests
            return

        cmd = cmd.upper()
        if cmd not in ['USER','PASS'] and not self.shell:                       # these are the only two commands that don't require
            log.debug('ftp_%s returning, user not logged in' % cmd)             # an authenticated user
            self.reply(NOT_LOGGED_IN)
            return

        if cmd in self.blockingCommands:                                        # if this is a DTP related command
            log.debug('FTP.processCommand: cmd %s in blockingCommands' % cmd)
            if not self.dtpInstance:                                            # if no one has connected yet
#                log.debug('FTP.processCommand: self.dtpInstance = %s' % self.dtpInstance)
                # a bit hackish, but manually blocks this command 
                # until we've set up the DTP protocol instance
                # _unblock will run this first command and subsequent
                self.blocked = [(cmd,args)]                                     # add item to queue and start blocking
#                log.debug('during dtp setup, blocked = %s' % self.blocked)
                return

#       TODO: vvvvv clean up crufty comment vvvvvv
#        method = getattr(self, "ftp_%s" % cmd, None)                            # try to find the method in this class
#        log.debug('FTP.processCommand: method = %s' % method)
#        if method:
#            return method(*args)                                                
        return getattr(self, "ftp_%s" % cmd, lambda *args: None)(*args)
        raise CmdNotImplementedError(cmd)                 # if we didn't find cmd, raise an error and alert client

    def _unblock(self, *_):
        commands, self.blocked = self.blocked, None
        while commands:
            if self.blocked is None:                         # while no other method has set self.blocked
                cmd, args = commands.pop(0)                  # pop a command off the queue and process it
                self.processCommand(cmd, *args)              
            else:                                            # if someone has blocked during the time we were processing
                self.blocked.extend(commands)                # add our commands that we dequeued back into the queue

# TODO: Re-implement DTP as an adapter to FTP-PI

#    def _createDTP(self):
#        self.setTimeout(None)     # don't timeOut when setting up DTP
#        log.debug('_createDTP')
#        if not self.dtpFactory:
#            phost = self.transport.getPeer()[1]
#            self.dtpFactory = DTPFactory(pi=self, peerHost=phost)
#            self.dtpFactory.setTimeout(self.dtpTimeout)
#        if not hasattr(self, 'TestingSoJustSkipTheReactorStep'):    # to allow for testing
#            if self.dtpTxfrMode == PASV:    
#                self.dtpPort = reactor.listenTCP(0, self.dtpFactory)
#            elif self.dtpTxfrMode == PORT: 
#                self.dtpPort = reactor.connectTCP(self.dtpHostPort[1], self.dtpHostPort[2])
#            else:
#                log.err('SOMETHING IS SCREWY: _createDTP')
#
#        d = self.dtpFactory.deferred        
#        d.addCallback(debugDeferred, 'dtpFactory deferred')
#        d.addCallback(self._unblock)                            # VERY IMPORTANT: call _unblock when client connects
#        d.addErrback(self._ebDTP)

#    def _ebDTP(self, error):
#        log.msg(error)
#        self.setTimeout(self.factory.timeOut)       # restart timeOut clock after DTP returns
#        r = error.trap(defer.TimeoutError,          # this is called when DTP times out
#                       BogusClientError,            # called if PI & DTP clients don't match
#                       FTPTimeoutError,             # called when FTP connection times out
#                       ClientDisconnectError)       # called if client disconnects prematurely during DTP transfer
#                       
#        if r == defer.TimeoutError:                     
#            self.reply(CANT_OPEN_DATA_CNX)
#        elif r in (BogusClientError, FTPTimeoutError):
#            self.reply(SVC_NOT_AVAIL_CLOSING_CTRL_CNX)
#            self.transport.loseConnection()
#        elif r == ClientDisconnectError:
#            self.reply(CNX_CLOSED_TXFR_ABORTED)

        # if we timeout, or if an error occurs, 
        # all previous commands are junked
#        self.blocked = None                         
        
#    def cleanupDTP(self):
#        """call when DTP connection exits
#        """
#        log.debug('cleanupDTP')
#
#        dtpPort, self.dtpPort = self.dtpPort, None
#        try:
#            dtpPort.stopListening()
#        except AttributeError, (e,):
#            log.msg('Already Called dtpPort.stopListening!!!: %s' % e)
#
#        self.dtpFactory.stopFactory()
#        if self.dtpFactory is None:
#            log.debug('ftp.dtpFactory already set to None')
#        else:
#            self.dtpFactory = None
#
#        if self.dtpInstance is None:
#            log.debug('ftp.dtpInstance already set to None')
#        else:
#            self.dtpInstance = None
#
#    def _doDTPCommand(self, cmd, *arg): 
#        self.setTimeout(None)               # don't Time out when waiting for DTP Connection
#        log.debug('FTP._doDTPCommand: self.blocked: %s' % self.blocked)
#        if self.blocked is None:
#            self.blocked = []
#        try:
#            f = getattr(self.dtpInstance, "dtp_%s" % cmd, None)
#            log.debug('running dtp function %s' % f)
#        except AttributeError, e:
#            log.err('SOMETHING IS SCREWY IN _doDTPCommand')
#            raise e
#        else:
#            self.dtpFactory.setTimeout(self.dtpTimeout)
#            if arg:
#                d = f(arg)
#            else:
#                d = f()
#            d.addCallback(debugDeferred, 'deferred returned to _doDTPCommand has fired')
#            d.addCallback(lambda _: self._cbDTPCommand())
#            d.addCallback(debugDeferred, 'running cleanupDTP')
#            d.addCallback(lambda _: self.cleanupDTP())
#            d.addCallback(debugDeferred, 'running ftp.setTimeout()')
#            d.addCallback(lambda _: self.setTimeout(self.factory.timeOut))
#            d.addCallback(debugDeferred, 'running ftp._unblock')
#            d.addCallback(lambda _: self._unblock())
#            d.addErrback(self._ebDTP)
#
#    def finishedFileTransfer(self, *arg):
#        """called back when a file transfer has been completed by the dtp"""
#        log.debug('finishedFileTransfer! cleaning up DTP')
#        if self.fp is not None and not self.fp.closed:
#            if self.fp.tell() == self.fpsize:
#                log.debug('transfer completed okay :-)')
#                self.reply(TXFR_COMPLETE_OK)
#            else:
#                log.debug("uh-oh there was an error...must have been the client's fault")
#                self.reply(CNX_CLOSED_TXFR_ABORTED)
#            self.fp.close()
#
#    def _cbDTPCommand(self):
#        """called back when any DTP command has completed successfully"""
#        log.debug("DTP Command success")

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
            raise CmdSyntaxError('no parameters')
        self.user = string.split(params)[0]
#        log.debug('ftp_USER params: %s' % params)
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)

    # TODO: add max auth try before timeout from ip...

    def ftp_PASS(self, params=''):
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
            raise BadCmdSequenceError('USER required before PASS')

#        log.debug('ftp_PASS params: %s' % params)

        if params == '':
            raise CmdArgSyntaxError('you must specify a password with PASS')
        
        self.passwd = params.split()[0]        # parse password 

        # if this is an anonymous login
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        IShell
                    ).addCallbacks(self._cbAnonLogin, self._ebLogin
                    )
            else:
                # if cred has been set up correctly, this shouldn't happen
                raise AuthorizationError('internal server error')

        # otherwise this is a user login
        else:
            if self.portal:
                self.portal.login(
                        credentials.UsernamePassword(self.user, self.passwd),
                        None,
                        IShell
                    ).addCallbacks(self._cbLogin, self._ebLogin
                    )
            else:
                raise AuthorizationError('internal server error')


    def _cbAnonLogin(self, (interface, avatar, logout)):
        """sets up anonymous login avatar"""
#        assert interface is IShell
        if interface is not IShell:
            raise NotImplementedError('interface must be or derive from ftp.IShell')

        peer = self.transport.getPeer()
#       log.debug("Anonymous login from %s:%s" % (peer[1], peer[2]))
        self.shell = avatar
        # XXX: Check to see if this is correct:
        #      should logout be assigned to avatar?
        self.shell.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        """sets up authorized user login avatar"""
        # XXX: How handle this exception?
        if interface is not IShell:
            raise NotImplementedError('interface must be or derive from ftp.IShell')
        self.shell = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure):
        r = failure.trap(cred_error.UnauthorizedLogin, TLDNotSetInRealmError)
        if r == TLDNotSetInRealmError:
            log.debug(failure.getErrorMessage())
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
            self.transport.loseConnection()
        else:
            self.reply(AUTH_FAILURE, '')

    def ftp_TYPE(self, params):
        p = params[0].upper()
        if p[0] not in ['I', 'A', 'L']:
            raise CmdArgSyntaxError(p[0])
        elif p[0] in ['I', 'L']:
            self.binary = True
            self.reply(TYPE_SET_OK, p)
        elif p[0] == 'A':
            self.binary = False
            self.reply(TYPE_SET_OK, p)
        else:
            raise CmdSyntaxError(p)

    def ftp_SYST(self, params=None):
        self.reply(NAME_SYS_TYPE)

    def ftp_LIST(self, params=''):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
#        log.debug('ftp_LIST: %s' % params)
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        self.fp, self.fpsize = self.shell.list(cleanPath(params))    # returns a StringIO object
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')

    def ftp_SIZE(self, params=''):
#        log.debug('ftp_SIZE: %s' % params)
        filesize = self.shell.size(cleanPath(params))
        self.reply(FILE_STATUS, filesize)

    def ftp_MDTM(self, params=''):
#        log.debug('ftp_MDTM: %s' % params)
        dtm = self.shell.mdtm(cleanPath(params))
        self.reply(FILE_STATUS, dtm)
 
    def ftp_PWD(self, params=''):
        """ Print working directory command
        """
        self.reply(PWD_REPLY, self.shell.pwd())

    def ftp_PASV(self):
        """Request for a passive connection

        reply is in format 227 =h1,h2,h3,h4,p1,p2

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
        # NOTE: Normally, the way DTP related commands work is that they
        # go through the PI processing (what goes on here), and then make
        # the appropriate call to _doDTPCommand. 
        # 
        # however, in this situation, since this is likely the first command
        # that will be run that has to do with the DTP factory, we
        # call _createDTP explicitly (as opposed to letting _doDTPCommand
        # do it for us).
        #
        # summary: this method is a special case, so keep that in mind
        #
        log.debug('ftp_PASV') 
        self.dtpTxfrMode = PASV

        # XXX: change as appropriate to refactoring

        if self.dtpFactory:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpFactory:             # if we haven't set up a DTP port yet (or just closed one)
            try:
                self._createDTP()
            except OSError, (e,):           # we're watching for a could not listen on port error
                log.msg("CRITICAL BUG!! THIS SHOULD NOT HAVE HAPPENED!!! %s" % e)
        sockname = self.transport.getHost()                # Use the ip from the PI-connection
        localip = string.replace(sockname[1], '.', ',')    # format the reply 
        lport = self.dtpPort.socket.getsockname()[1]
        lp1 = lport / 256                                  # convert port into two 8-byte values
        lp2, lp1 = str(lport - lp1*256), str(lp1)
        self.reply(ENTERING_PASV_MODE, "%s,%s,%s" % (localip, lp1, lp2))
        log.debug("passive port open on: %s:%s" % (localip, lport), level="debug")

    def decodeHostPort(self, line):
        """Decode an FTP response specifying a host and port.
        
        see RFC sec. 4.1.2 "PASV"

        @returns: a 2-tuple of (host, port).
        """
        #abcdef = re.sub('[^0-9, ]', '', line[4:])
        abcdef = re.sub('[^0-9, ]', '', line)
        a, b, c, d, e, f = map(str.strip, abcdef.split(','))
        host = "%s.%s.%s.%s" % (a, b, c, d)
        port = (int(e)<<8) + int(f)
        return (host, port)

    def ftp_PORT(self, params):

        # XXX: change as appropriate to refactoring

        log.debug('ftp_PORT')
        self.dtpTxfrMode = PORT
        self.dtpHostPort = self.decodeHostPort(params)
        if self.dtpFactory:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpFactory:             # if we haven't set up a DTP port yet (or just closed one)
            try:
                self._createDTP()
            except OSError, (e,):           # we're watching for a could not listen on port error
                log.msg("CRITICAL BUG!! THIS SHOULD NOT HAVE HAPPENED!!! %s" % e)
        self.reply(PORT_MODE_OK)


    def ftp_CWD(self, params):
        self.shell.cwd(cleanPath(params))
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)


    def ftp_CDUP(self):
        self.shell.cdup()
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)


    def ftp_RETR(self, params):

        # XXX: change as appropriate to refactoring

        if self.dtpTxfrMode is None:
            raise BadCmdSequenceError('must send PORT or PASV before RETR')
        self.fp, self.fpsize = self.shell.retr(cleanPath(params))
        log.debug('self.fp = %s, self.fpsize = %s' % (self.fp, self.fpsize))
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')


    def ftp_STRU(self, params=""):
        p = params.upper()
        if params == 'F': return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)


    def ftp_MODE(self, params=""):
        p = params.upper()
        if params == 'S': return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)


    def ftp_QUIT(self, params=''):
        self.transport.loseConnection()
        log.debug("Client Quit")


class Factory(protocol.Factory):
    """A factory for producing ftp protocol instances
    @ivar maxProtocolInstances: the maximum number of FTP protocol instances
        this factory will create. When the maximum number is reached, a protocol
        instance will be spawned that will give the "Too many connections" message
        to the client and then close the connection.
        Set to None for unlimited connections
    @ivar timeOut: the protocol's idle timeout time in seconds, default is 600 seconds
    """
    protocol = FTP
    allowAnonymous = True
    userAnonymous = None
    timeOut = 600

    _maxProtocolInstances = None
    _currentInstanceNum = 0
    _instances = []

    # if no anonymousUserName is specified, 
    # no anonymous logins allowed
    def __init__(self, portal=None, anonymousUserName=None, 
                       maxProtocolInstances=None):
        self.portal = portal
        self.userAnonymous = anonymousUserName
        if anonymousUserName is None:
            self.allowAnonymous = False
        self._maxProtocolInstances = maxProtocolInstances
        reactor._pi = self

    def buildProtocol(self, addr):
        log.debug('%s of %s max ftp instances: ' % (self._currentInstanceNum, self._maxProtocolInstances))
        pi            = protocol.Factory.buildProtocol(self, addr)
        pi.protocol   = self.protocol
        pi.portal     = self.portal
        pi.timeOut    = Factory.timeOut
        pi.factory    = self
        if self._maxProtocolInstances is not None:
            self._currentInstanceNum += 1
            pi._instanceNum = self._currentInstanceNum
        self._instances.append(pi)
        return pi

    def stopFactory(self):
        # make sure ftp instance's timeouts are set to None
        # to avoid reactor complaints
        [p.setTimeout(None) for p in self._instances if p.timeOut is not None]

FTPFactory = Factory
        
# -- Cred Objects --


