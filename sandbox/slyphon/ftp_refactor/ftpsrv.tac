# Import modules
from twisted.application import service, internet
from twisted.internet import protocol
from twisted.manhole import telnet
from twisted.application import strports

from twisted.cred import error
from twisted.cred import portal
from twisted.cred import checkers
from twisted.cred import credentials

import os.path, os

from ftp import FTP, Factory, IShell
from ftpdav import AnonymousShell, Realm


# Construct the application
application = service.Application("ftpserver")

# Get the IServiceCollection interface
myService = service.IServiceCollection(application)

# Create the protocol factory
ftpFactory = Factory()
realm = Realm(os.getcwd())
p = portal.Portal(realm)
p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

ftpFactory.portal = p
ftpFactory.protocol = FTP
ftpFactory.timeOut = 10

# Create the (sole) server
port = 2121
if os.getuid() == 0:        # if we're root
    port = 21               # use the privileged port

myServer = internet.TCPServer(port, ftpFactory)

# Tie the service to the application
myServer.setServiceParent(myService)

# this is a manhole-telnet server for debugging
#t = telnet.ShellFactory()
#t.pi = ftpFactory
#t.username, t.password = "jds", "jds"
#s = strports.service('2112', t)
#t.setService(s)
#s.setServiceParent(myService)
#import gc
#def logobjects(self):
#    log.msg('gc.get_objecte: %s' % gc.get_objects())

#from twisted.application.internet import TimerService
#TimerService.step = 1000
#TimerService.callable = logobjects
#ts = TimerService(1000, logobjects)
#ts.setServiceParent(myService)


# vim:ft=python
