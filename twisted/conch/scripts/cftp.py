# -*- test-case-name: twisted.conch.test.test_sftp -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# $Id: cftp.py,v 1.65 2004/03/11 00:29:14 z3p Exp $

#""" Implementation module for the `cftp` command.
#"""
from twisted.conch.client import agent, connect, default, options
from twisted.conch.error import ConchError
from twisted.conch.ssh import connection, common
from twisted.conch.ssh import channel, filetransfer
from twisted.protocols import basic
from twisted.internet import reactor, stdio, defer, utils
from twisted.python import log, usage, failure

import os, sys, getpass, struct, tty, fcntl, base64, signal, stat, errno
import fnmatch, pwd

class ClientOptions(options.ConchOptions):
    
    synopsis = """Usage:   cftp [options] [user@]host
         cftp [options] [user@]host[:dir[/]]
         cftp [options] [user@]host[:file [localfile]]
"""
    
    optParameters = options.ConchOptions.optParameters + \
                    [
                    ['buffersize', 'B', 32768, 'Size of the buffer to use for sending/receiving.'],
                    ['batchfile', 'b', None, 'File to read commands from, or \'-\' for stdin.'],
                    ['requests', 'R', 5, 'Number of requests to make before waiting for a reply.'],
                    ['subsystem', 's', 'sftp', 'Subsystem/server program to connect to.']]

    def parseArgs(self, host, localPath=None):
        self['remotePath'] = ''
        if ':' in host:
            host, self['remotePath'] = host.split(':', 1)
            self['remotePath'].rstrip('/')
        self['host'] = host
        self['localPath'] = localPath 

def run():
    args = sys.argv[1:]
    if '-l' in args: # cvs is an idiot
        i = args.index('-l')
        args = args[i:i+2]+args
        del args[i+2:i+4]
    options = ClientOptions()
    try:
        options.parseOptions(args)
    except usage.UsageError, u:
        print 'ERROR: %s' % u
        sys.exit(1)
    if options['log']:
        realout = sys.stdout
        log.startLogging(sys.stderr)
        sys.stdout = realout
    else:
        log.discardLogs()
    doConnect(options)
    reactor.run()

def handleError():
    from twisted.python import failure
    global exitStatus
    exitStatus = 2
    try:
        reactor.stop()
    except: pass
    log.err(failure.Failure())
    raise

def doConnect(options):
#    log.deferr = handleError # HACK
    if '@' in options['host']:
        options['user'], options['host'] = options['host'].split('@',1)
    host = options['host']
    if not options['user']:
        options['user'] = getpass.getuser() 
    if not options['port']:
        options['port'] = 22
    else:
        options['port'] = int(options['port'])
    host = options['host']
    port = options['port']
    conn = SSHConnection()
    conn.options = options
    vhk = default.verifyHostKey
    uao = default.SSHUserAuthClient(options['user'], options, conn)
    connect.connect(host, port, options, vhk, uao).addErrback(_ebExit)

def _ebExit(f):
    #global exitStatus
    if hasattr(f.value, 'value'):
        s = f.value.value
    else:
        s = str(f)
    print s
    #exitStatus = "conch: exiting with error %s" % f
    try:
        reactor.stop()
    except: pass

def _ignore(*args): pass

class StdioClient(basic.LineReceiver):

    ps = 'cftp> '
    delimiter = '\n'

    def __init__(self, client, f = None):
        self.client = client
        self.currentDirectory = ''
        self.file = f

    def connectionMade(self):
        self.client.realPath('').addCallback(self._cbSetCurDir)

    def _cbSetCurDir(self, path):
        self.currentDirectory = path
        self._newLine()

    def lineReceived(self, line):
        if self.client.transport.localClosed:
            return
        log.msg('got line %s' % repr(line))
        line = line.lstrip()
        if not line:
            self._newLine()
            return
        if self.file and line.startswith('-'):
            self.ignoreErrors = 1
            line = line[1:]
        else:
            self.ignoreErrors = 0
        if ' ' in line:
            command, rest = line.split(' ', 1)
            rest = rest.lstrip()
        else:
            command, rest = line, ''
        if command.startswith('!'): # command
            f = self.cmd_EXEC
            rest = (command[1:] + ' ' + rest).strip()
        else:
            command = command.upper()
            log.msg('looking up cmd %s' % command)
            f = getattr(self, 'cmd_%s' % command, None)
        if f is not None:
            d = defer.maybeDeferred(f, rest)
            d.addCallback(self._cbCommand)
            d.addErrback(self._ebCommand)
        else:
            self._ebCommand(failure.Failure(NotImplementedError(
                "No command called `%s'" % command)))
            self._newLine()

    def _newLine(self):
        if self.client.transport.localClosed:
            return
        self.transport.write(self.ps)
        self.ignoreErrors = 0
        if self.file:
            l = self.file.readline()
            if not l:
                self.client.transport.loseConnection()
            else:
                self.transport.write(l)
                self.lineReceived(l.strip())

    def _cbCommand(self, result):
        if result is not None:
            self.transport.write(result)
            if not result.endswith('\n'):
                self.transport.write('\n')
        self._newLine()

    def _ebCommand(self, f):
        log.msg(f)
        e = f.trap(NotImplementedError, filetransfer.SFTPError, OSError, IOError)
        if e == NotImplementedError:
            self.transport.write(self.cmd_HELP(''))
        elif e == filetransfer.SFTPError:
            self.transport.write("remote error %i: %s\n" % 
                    (f.value.code, f.value.message))
        elif e in (OSError, IOError):
            self.transport.write("local error %i: %s\n" %
                    (f.value.errno, f.value.strerror))
        if self.file and not self.ignoreErrors:
            self.client.transport.loseConnection()
        self._newLine()

    def cmd_CD(self, path):
        if not path.endswith('/'):
            path += '/'
        newPath = path and os.path.join(self.currentDirectory, path) or ''
        d = self.client.openDirectory(newPath)
        d.addCallback(self._cbCd)
        d.addErrback(self._ebCommand)
        return d

    def _cbCd(self, directory):
        directory.close()
        d = self.client.realPath(directory.name)
        d.addCallback(self._cbCurDir)
        return d

    def _cbCurDir(self, path):
        self.currentDirectory = path

    def cmd_CHGRP(self, rest):
        grp, path = rest.split(' ', 1)
        grp = int(grp)
        d = self.client.getAttrs(path)
        d.addCallback(self._cbSetUsrGrp, path, grp=grp)
        return d
    
    def cmd_CHMOD(self, rest):
        mod, path = rest.split(' ', 1)
        mod = int(mod, 8)
        d = self.client.setAttrs(path, {'permissions':mod})
        d.addCallback(_ignore)
        return d
    
    def cmd_CHOWN(self, rest):
        usr, path = rest.split(' ', 1)
        usr = int(usr)
        d = self.client.getAttrs(path)
        d.addCallback(self._cbSetUsrGrp, path, usr=usr)
        return d
    
    def _cbSetUsrGrp(self, attrs, path, usr=None, grp=None):
        new = {}
        new['uid'] = (usr is not None) and usr or attrs['uid']
        new['gid'] = (grp is not None) and grp or attrs['gid']
        d = self.client.setAttrs(path, new)
        d.addCallback(_ignore)
        return d

    def cmd_GET(self, rest):
        if ' ' in rest:
            remote, local = rest.split()
        else:
            remote = local = rest
        lf = file(local, 'w')
        path = os.path.join(self.currentDirectory, remote)
        d = self.client.openFile(path, filetransfer.FXF_READ, {})
        d.addCallback(self._cbGetOpenFile, lf)
        d.addErrback(self._ebCloseLf, lf)
        return d

    def _ebCloseLf(self, f, lf):
        lf.close()
        return f

    def _cbGetOpenFile(self, rf, lf):
        bufferSize = self.client.transport.conn.options['buffersize']
        numRequests = self.client.transport.conn.options['requests']
        dList = []
        chunks = []
        for i in range(numRequests):            
            d = self._cbGetRead('', rf, lf, chunks, 0, bufferSize)
            dList.append(d)
        dl = defer.DeferredList(dList, fireOnOneErrback=1)
        dl.addCallback(self._cbGetDone, rf, lf)
        return dl

    def _getNextChunk(self, chunks):
        end = 0
        for chunk in chunks:
            if end == 'eof':
                return # nothing more to get
            if end != chunk[0]:
                i = chunks.index(chunk)
                chunks.insert(i, (end, chunk[0]))
                return (end, chunk[0] - end)
            end = chunk[1]
        bufSize = self.client.transport.conn.options['buffersize']
        chunks.append((end, end + bufSize))
        return (end, bufSize)

    def _cbGetRead(self, data, rf, lf, chunks, start, size):
        if data and isinstance(data, failure.Failure):
            log.msg('get read err: %s' % data)
            reason = data
            reason.trap(EOFError)
            i = chunks.index((start, start + size))
            del chunks[i]
            chunks.insert(i, (start, 'eof'))
        elif data:
            log.msg('get read data: %i' % len(data))
            lf.seek(start)
            lf.write(data)
            if len(data) != size:
                log.msg('got less than we asked for: %i < %i' % 
                        (len(data), size))
                i = chunks.index((start, start + size))
                del chunks[i]
                chunks.insert(i, (start, start + len(data)))
        chunk = self._getNextChunk(chunks)
        if not chunk:
            return
        else:
            start, length = chunk
        log.msg('asking for %i -> %i' % (start, start+length))
        d = rf.readChunk(start, length)
        d.addBoth(self._cbGetRead, rf, lf, chunks, start, length)
        return d

    def _cbGetDone(self, ignored, rf, lf):
        log.msg('get done')
        rf.close()
        lf.close()
        return "transferred %s to %s" % (rf.name, lf.name)
   
    def cmd_PUT(self, rest):
        if ' ' in rest:
            local, remote= rest.split()
        else:
            remote = local = rest
        lf = file(local, 'r')
        path = os.path.join(self.currentDirectory, remote)
        d = self.client.openFile(path, filetransfer.FXF_WRITE|filetransfer.FXF_CREAT, {})
        d.addCallback(self._cbPutOpenFile, lf)
        d.addErrback(self._ebCloseLf, lf)
        return d

    def _cbPutOpenFile(self, rf, lf):
        numRequests = self.client.transport.conn.options['requests']
        dList = []
        chunks = []
        for i in range(numRequests):
            d = self._cbPutWrite(None, rf, lf, chunks)
            if d:
                dList.append(d)
        dl = defer.DeferredList(dList, fireOnOneErrback=1)
        dl.addCallback(self._cbPutDone, rf, lf)
        return dl

    def _cbPutWrite(self, ignored, rf, lf, chunks):
        chunk = self._getNextChunk(chunks)
        start, size = chunk
        lf.seek(start)
        data = lf.read(size)
        if data:
            d = rf.writeChunk(start, data)
            d.addCallback(self._cbPutWrite, rf, lf, chunks)
            return d
        else:
            return

    def _cbPutDone(self, ignored, rf, lf):
        lf.close()
        rf.close()
        return 'transferred %s to %s' % (lf.name, rf.name)

        
    def cmd_LCD(self, path):
        os.chdir(path)

    def cmd_LN(self, rest):
        linkpath, targetpath = rest.split(' ')
        return self.client.makeLink(linkpath, targetpath).addCallback(_ignore)

    def cmd_LS(self, rest):
        # possible lines:
        # ls                    current directory
        # ls name_of_file       that file
        # ls name_of_directory  that directory
        # ls some_glob_string   current directory, globbed for that string
        rest += ' '
        if rest.startswith('-l '):
            verbose = 1
            rest = rest[3:]
        else:
            verbose = 0 
        rest = rest[:-1]
        fullPath = os.path.join(self.currentDirectory, rest)
        head, tail = os.path.split(fullPath)
        if '*' in tail or '?' in tail:
            glob = 1
        else:
            glob = 0
        log.msg(str((fullPath, head, tail, verbose, tail, glob)))
        if tail and not glob: # could be file or directory
           # try directory first
           d = self.client.openDirectory(fullPath)
           d.addCallback(self._cbOpenList, tail, verbose)
           d.addErrback(self._ebNotADirectory, head, tail, verbose)
        else:
            d = self.client.openDirectory(head)
            d.addCallback(self._cbOpenList, tail, verbose)
        return d

    def _cbOpenList(self, directory, glob, verbose):
        files = []
        if not glob:
            glob = "[!.]*"
        d = directory.read()
        d.addBoth(self._cbReadFile, files, directory, glob, verbose)
        return d

    def _ebNotADirectory(self, reason, path, glob, verbose):
        d = self.client.openDirectory(path)
        d.addCallback(self._cbOpenList, glob, verbose)
        return d

    def _cbReadFile(self, files, l, directory, glob, verbose):
        if not isinstance(files, failure.Failure):
            l.extend([f for f in files if fnmatch.fnmatch(f[0], glob)])
            d = directory.read()
            d.addBoth(self._cbReadFile, l, directory, glob, verbose)
            return d
        else:
            reason = files
            reason.trap(EOFError)
            directory.close()
            return self._cbDisplayFiles(l, glob, verbose)

    def _cbDisplayFiles(self, files, glob, verbose):
        files.sort()
        if verbose:
            lines = [f[1] for f in files]
        else:
            lines = [f[0] for f in files]
        if not lines:
            return None
        else:
            return '\n'.join(lines)

    def cmd_MKDIR(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.makeDirectory(path, {}).addCallback(_ignore)

    def cmd_RMDIR(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.removeDirectory(path).addCallback(_ignore)

    def cmd_LMKDIR(self, path):
        os.system("mkdir %s" % path)

    def cmd_RM(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.removeFile(path).addCallback(_ignore)

    def cmd_LLS(self, rest):
        os.system("ls %s" % rest)

    def cmd_RENAME(self, rest):
        oldpath, newpath = rest.split(' ')
        return self.client.renameFile(oldpath, newpath).addCallback(_ignore)

    def cmd_EXIT(self, ignored):
        self.client.transport.loseConnection()

    cmd_QUIT = cmd_EXIT

    def cmd_VERSION(self, ignored):
        return "SFTP version %i" % self.client.version
    
    def cmd_HELP(self, ignored):
        return """Available commands:
cd path                         Change remote directory to 'path'.
chgrp gid path                  Change gid of 'path' to 'gid'.
chmod mode path                 Change mode of 'path' to 'mode'.
chown uid path                  Change uid of 'path' to 'uid'.
exit                            Disconnect from the server.
get remote-path [local-path]    Get remote file.
help                            Get a list of available commands.
lcd path                        Change local directory to 'path'.
lls [ls-options] [path]         Display local directory listing.
lmkdir path                     Create local directory.
ln linkpath targetpath          Symlink remote file.
lpwd                            Print the local working directory.
ls [-l] [path]                  Display remote directory listing.
mkdir path                      Create remote directory.
put local-path [remote-path]    Put local file.
pwd                             Print the remote working directory.
quit                            Disconnect from the server.
rename oldpath newpath          Rename remote file.
rmdir path                      Remove remote directory.
rm path                         Remove remote file.
version                         Print the SFTP version.
?                               Synonym for 'help'.
"""

    def cmd_PWD(self, ignored):
        return self.currentDirectory

    def cmd_LPWD(self, ignored):
        return os.getcwd()

    def cmd_EXEC(self, rest):
        shell = pwd.getpwnam(getpass.getuser())[6]
        print repr(rest)
        if rest:
            cmds = ['-c', rest]
            return utils.getProcessOutput(shell, cmds, errortoo=1)
        else:
            os.system(shell)

StdioClient.__dict__['cmd_?'] = StdioClient.cmd_HELP

class SSHConnection(connection.SSHConnection):
    def serviceStarted(self):
        self.openChannel(SSHSession())

class SSHSession(channel.SSHChannel):

    name = 'session'

    def channelOpen(self, foo):
        log.msg('session %s open' % self.id)
        if self.conn.options['subsystem'].startswith('/'):
            request = 'exec'
        else:
            request = 'subsystem'
        d = self.conn.sendRequest(self, request, \
            common.NS(self.conn.options['subsystem']), wantReply=1)
        d.addCallback(self._cbSubsystem)
        d.addErrback(_ebExit)

    def _cbSubsystem(self, result):
        self.client = filetransfer.FileTransferClient()
        self.client.makeConnection(self)
        self.dataReceived = self.client.dataReceived
        f = None
        if self.conn.options['batchfile']:
            fn = self.conn.options['batchfile']
            if fn != '-':
                f = file(fn)
        self.stdio = stdio.StandardIO(StdioClient(self.client, f))

    def extReceived(self, t, data):
        if t==connection.EXTENDED_DATA_STDERR:
            log.msg('got %s stderr data' % len(data))
            sys.stderr.write(data)
            sys.stderr.flush()

    def eofReceived(self):
        log.msg('got eof')
        self.stdio.closeStdin()
    
    def closeReceived(self):
        log.msg('remote side closed %s' % self)
        self.conn.sendClose(self)

    def closed(self):
        try:
            reactor.stop()
        except:
            pass

    def stopWriting(self):
        self.stdio.stopReading()

    def startWriting(self):
        self.stdio.startReading()

if __name__ == '__main__':
    run()

