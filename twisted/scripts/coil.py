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

""" Implementation module for the `coil` command.
"""

# twisted imports
from twisted.python import usage, plugin
from twisted.internet import app, main
from twisted.web import server
from twisted.coil import web

# system imports
import sys, os, pickle


class Options(usage.Options):
    """Options for coil command."""
    
    synopsis="""\
Usage:

  coil [--new=<application name>] <tap file>

"""
    
    optParameters = [["new", "n", None],
                     ["port", "p", 9080]]
    
    optFlags = [["localhost", "l"]]

    def parseArgs(self, tapFile):
        self.opts['tapFile'] = tapFile

    def postOptions(self):
        tapFile = self.opts['tapFile']
        new = self.opts['new']
        if not os.path.exists(tapFile) and not new:
            raise usage.UsageError, "No such file: %s" % repr(tapFile)
        if os.path.exists(tapFile) and new:
            raise usage.UsageError, "File %s already exists." % repr(tapFile)


def run():
    """Run the coil command-line app."""
    # parse the command line options
    config = Options()
    try:
        config.parseOptions(sys.argv[1:])
    except:
        print str(sys.exc_value)
        print
        print str(config)
        sys.exit(2)

    new = config.opts['new']
    tapFile = config.opts['tapFile']
    
    # load or create the Application instance to be configured
    if new:
        application = app.Application(new)
    else:
        f = open(tapFile, "rb")
        application = pickle.loads(f.read())
        f.close()
        if not isinstance(application, app.Application):
            raise TypeError, "The loaded object %s is not a twisted.internet.app.Application instance." % application
    
    # setup shutdown hook that saves the created tap
    f = lambda a=application, filename=tapFile: a.save(filename=filename)
    main.callBeforeShutdown(f)

    # load plugins that come with Twisted
    for p in plugin.getPlugIns('coil'):
        if p.module[:21] == "twisted.coil.plugins." and not p.isLoaded():
            p.load()
    
    # create the coil webserver
    coilApp = app.Application("coil")
    root = web.ConfigRoot(application)
    site = server.Site(root)
    if config.opts['localhost']:
        interface = '127.0.0.1'
    else:
        interface = ''
    coilApp.listenTCP(int(config.opts['port']), site, interface=interface)
    coilApp.run(save=0)
