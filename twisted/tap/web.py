
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
from twisted.internet import tcp
from twisted.python import usage, reflect
from twisted.spread import pb

import sys


class Options(usage.Options):
    synopsis = "Usage: mktap web [options]"
    optParameters = [["port", "p", "8080","Port to start the server on."],
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

    def __init__(self):
        usage.Options.__init__(self)
        self.opts['indexes'] = []
        self.opts['root'] = None

    def opt_index(self, indexName):
        """Add the name of a file used to check for directory indexes.
        [default: index, index.html]
        """
        self.opts['indexes'].append(indexName)

    opt_i = opt_index
        
    def opt_user(self):
        """Makes a server with ~/public_html and ~/.twistd-web-service support for users.
        """
        self.opts['root'] = distrib.UserDirectory()

    opt_u = opt_user

    def opt_path(self, path):
        """<path> is either a specific file or a directory to
        be set as the root of the web server. Use this if you
        have a directory full of HTML, cgi, php3, epy, or rpy files or
        any other files that you want to be served up raw.
        """

        self.opts['root'] = static.File(os.path.abspath(path))
        self.opts['root'].processors = {
            '.cgi': twcgi.CGIScript,
            '.php3': twcgi.PHPScript,
            '.epy': script.PythonScript
            }

    def opt_static(self, path):
        """Same as --path, this is deprecated and will be removed in a
        future release."""
        print ("WARNING: --static is deprecated and will be removed in"
               "a future release. Please use --path.")
        self.opt_path(path)
    opt_s = opt_static

    
    def opt_class(self, className):
        """Create a Resource subclass with a zero-argument constructor.
        """
        classObj = reflect.namedClass(className)
        self.opts['root'] = classObj()



    def opt_mime_type(self, defaultType):
        """Specify the default mime-type for static files."""
        if not isinstance(self.opts['root'], static.File):
            print "You can only use --mime_type after --path."
            sys.exit(2)
        self.opts['root'].defaultType = defaultType
    opt_m = opt_mime_type


    def opt_allow_ignore_ext(self):
        """Specify wether or not a request for 'foo' should return 'foo.ext'"""
        if not isinstance(self.opts['root'], static.File):
            print "You can only use --allow_ignore_ext after --path."
            sys.exit(2)
        self.opts['root'].allowExt = 1


def updateApplication(app, config):
    if config.opts['telnet']:
        from twisted.protocols import telnet
        factory = telnet.ShellFactory()
        app.listenTCP(int(config.opts['telnet']), factory)
    if config.opts['root']:
        root = config.opts['root']
        if config.opts['indexes']:
            config.opts['root'].indexNames = config.opts['indexes']
    else:
        # This really ought to be web.Admin or something
        root = test.Test()

    site = server.Site(root)

    if config.opts['personal']:
        import pwd,os

        pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                 = pwd.getpwuid(os.getuid())
        app.listenTCP(os.path.join(pw_dir,
                                   distrib.UserDirectory.userSocketName),
                      pb.BrokerFactory(distrib.ResourcePublisher(site)))
    else:
        app.listenTCP(int(config.opts['port']), site)

