# Import modules
from twisted.application import service, internet
from twisted.protocols import ftp
from twisted.internet import protocol

# Construct the application
application = service.Application("ftpserver")


# Get the IServiceCollection interface
myService = service.IServiceCollection(application)

# Create the protocol factory
ftpFactory = ftp.FTPFactory()
ftpFactory.root = '/home/jonathan'
ftpFactory.protocol = ftp.FTP

# Create the (sole) server
myServer = internet.TCPServer(2121, ftpFactory)

# Tie the service to the application
myServer.setServiceParent(myService)

# vim:ft=python
