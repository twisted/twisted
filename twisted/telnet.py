
"""A telnet python shell server, implemented over twisted.protocols.telnet.
"""

import string
import socket
import errno
import traceback
import copy

from twisted import net
from twisted import log
from cStringIO import StringIO
from twisted.protocols import telnet


class Shell(telnet.Telnet):

    def authenticate(self, username, password):
        return ((self.transport.server.username == username) and
                password == self.server.password)

    def processCommand(self, cmd):
        fn = '$telnet$'
        try:
            code = compile(cmd,fn,'eval')
        except:
            try:
                code = compile(cmd, fn, 'single')
            except:
                io = StringIO()
                traceback.print_exc(file=io)
                self.transport.write(io.getvalue()+'\r\n')
                return "Command"
        try:
            val, output = log.output(eval, code, self.server.namespace)
            self.transport.write(output)

            if val is not None:
                self.transport.write(repr(val))
            self.transport.write('\r\n')
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            self.transport.write(io.getvalue()+'\r\n')

        return "Command"


class Server(net.TCPServer):
    protocol = Shell
    username = "admin"
    password = "admin"

    def __init__(self, *args, **kw):
        apply(net.TCPServer.__init__, (self,)+args, kw)
        self.namespace = {}

    def __getstate__(self):
        """telnet.Server.__getstate__() -> dictionary
        This returns the persistent state of this server
        """
        # TODO -- refactor this and twisted.library.author.Author to use common
        # functionality (perhaps the 'code' module?)
        dict = net.TCPServer.__getstate__(self)
        ns = copy.copy(dict['namespace'])
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict

