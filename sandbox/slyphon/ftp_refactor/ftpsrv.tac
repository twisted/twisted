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

from jdftp import FTP, FTPFactory, IFTPShell, FTPAnonymousShell, FTPRealm


# Construct the application
application = service.Application("ftpserver")

# Get the IServiceCollection interface
myService = service.IServiceCollection(application)

# Create the protocol factory
ftpFactory = FTPFactory()
p = portal.Portal(FTPRealm())
p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

ftpFactory.portal = p
ftpFactory.protocol = FTP

# Create the (sole) server
port = 2121
if os.getuid() == 0:        # if we're root
    port = 21               # use the priviledged port

myServer = internet.TCPServer(port, ftpFactory)

# Tie the service to the application
myServer.setServiceParent(myService)

t = telnet.ShellFactory()
t.pi = ftpFactory
t.username, t.password = "jds", "jds"
s = strports.service('2112', t)
t.setService(s)
s.setServiceParent(myService)


# vim:ft=python
