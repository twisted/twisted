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
from twisted.python import usage
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
    
    def parseArgs(self, tapFile):
        self.tapFile = tapFile

    def postOptions(self):
        if not os.path.exists(self.tapFile) and not self.new:
            raise usage.UsageError, "No such file: %s" % repr(self.tapFile)
        if os.path.exists(self.tapFile) and self.new:
            raise usage.UsageError, "File %s already exists." % repr(self.tapFile)


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

    # load or create the Application instance to be configured
    if config.new:
        application = app.Application(config.new)
    else:
        f = open(config.tapFile, "rb")
        application = pickle.loads(f.read())
        f.close()
        if not isinstance(application, app.Application):
            raise TypeError, "The loaded object %s is not a twisted.internet.app.Application instance." % application
    
    # setup shutdown hook that saves the created tap
    f = lambda a=application, filename=config.tapFile: a.save(filename=filename)
    main.callBeforeShutdown(f)
    
    # create the coil webserver
    coilApp = app.Application("coil")
    root = web.ConfigRoot(application)
    site = server.Site(root)
    coilApp.listenTCP(int(config.port), site)
    coilApp.run(save=0)
