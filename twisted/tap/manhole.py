
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
I am the support module for making a manhole server with mktap.
"""

from twisted.manhole import service
from twisted.cred import authorizer
from twisted.spread import pb
from twisted.python import usage
import getpass, os, sys


class Options(usage.Options):
    synopsis = "mktap manhole [options]"
    optParameters = [["user", "u", "admin", "Name of user to allow to log in"]]
    def opt_port(self, opt):
        try:
            self.opts['portno'] = int(opt)
        except ValueError:
            raise usage.error("Invalid argument to 'port'!")

    def opt_password(self, password):
        """Required.  '-' will prompt or read a password from stdin.
        """
        # If standard input is a terminal, I prompt for a password and
        # confirm it.  Otherwise, I use the first line from standard
        # input, stripping off a trailing newline if there is one.
        if password in ('', '-'):
            if os.isatty(sys.stdin.fileno()):
                gotit = 0
                while not gotit:
                    try1 = getpass.getpass()
                    try2 = getpass.getpass("Confirm: ")
                    if try1 == try2:
                        gotit = 1
                    else:
                        sys.stderr.write("Passwords don't match.\n")
                else:
                    self.opts['password'] = try1
            else:
                self.opts['password'] = sys.stdin.readline()
                if self.opts['password'][-1] == '\n':
                    self.opts['password'] = self.opts['password'][:-1]
        else:
            self.opts['password'] = password

    def postOptions(self):
        if not self.opts.has_key('password'):
            self.opt_password('-')

    opt_p = opt_port
    opt_w = opt_password


def updateApplication(app, config):
    auth = authorizer.DefaultAuthorizer(app)
    svc = service.Service("twisted.manhole", serviceParent=app,
                          authorizer=auth)
    p = svc.createPerspective(config.opts['user'])
    p.makeIdentity(config.opts['password'])
    try:
        portno = config.opts['portno']
    except KeyError:
        portno = pb.portno
    app.listenTCP(portno, pb.BrokerFactory(pb.AuthRoot(auth)))
