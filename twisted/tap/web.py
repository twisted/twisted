
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

"""I am the support module for creating web servers with 'mktap'
"""

import string, os

# Twisted Imports
from twisted.web import server, static, twcgi, script, test, distrib
from twisted.internet import tcp, passport
from twisted.python import usage
from twisted.spread import pb

import sys


class Options(usage.Options):
    synopsis = "Usage: mktap web [options]"
    optStrings = [["port", "p", "8080","Port to start the server on."],
                  ["index","i", "index.html",
                   "Use an index name other than \"index.html\"."],
                  ["telnet", "t", None,
                   "Run a telnet server on this port."]]
    optFlags = [["personal", "",
                 "Instead of generating a webserver, generate a "
                 "ResourcePublisher which listens on "
                 "~/.twistd-web-service"]]

    longdesc = """\
This creates a web.tap file that can be used by twistd.  If you specify
no arguments, it will be a demo webserver that has the Test class from
twisted.web.test in it."""

    #def opt_help(self):
    #    print usage_message
    #    sys.exit(0)

    def opt_user(self):
        """Makes a server with ~/public_html and ~/.twistd-web-service support for users.
        """
        self.root = distrib.UserDirectory()

    opt_u = opt_user

    def opt_static(self, path):
        """<path> is either a specific file or a directory to
        be set as the root of the web server. Use this if you
        have a directory full of HTML, cgi, or php3 files or
        any other files that you want to be served up raw.
        """

        self.root = static.File(path)
        self.root.processors = {
            '.cgi': twcgi.CGIScript,
            '.php3': twcgi.PHPScript,
            '.epy': script.PythonScript
            }

    opt_s = opt_static

#    def opt_telnet(self, port):
#        from twisted.protocols import telnet
#        factory = telnet.ShellFactory()
#        app.addPort(tcp.Port(int(port), factory))

#    opt_t = opt_telnet



def getPorts(app, config):
    ports = []
    if config.telnet:
        from twisted.protocols import telnet
        factory = telnet.ShellFactory()
        ports.append((int(config.telnet), factory))
    try:
        root = config.root
        config.root.indexName = config.index
    except AttributeError:
        # This really ought to be web.Admin or something
        root = test.Test()

    site = server.Site(root)

    if config.personal:
        import pwd,os

        pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                 = pwd.getpwuid(os.getuid())
        ports.append((os.path.join(pw_dir,
                                   distrib.UserDirectory.userSocketName),
                      pb.BrokerFactory(distrib.ResourcePublisher(site))))
    else:
        ports.append((int(config.port), site))
    return ports
