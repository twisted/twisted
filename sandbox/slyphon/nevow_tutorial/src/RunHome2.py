#!/usr/bin/env python2.3

from twisted.application import service, internet
from twisted.web import server, static, util, twcgi
from HomePage import HomePage
from storage import CSVStorage, RDBStorage

# CSVStorage is the storage object we wish to use for this application,
# If we wanted to use a different one, we could just drop it in here
# and the program would use that one (for instance, an RDBMS)
#
resource = HomePage(storage=CSVStorage.CSVStorage('storage/'))
#resource = HomePage(storage=RDBStorage.RDBStorage())

# We create a new twisted.web.server.Site by passing it
# an instance of the root page of our Woven application
# 
# site is actually a factory for HTTPChannels, but is not named
# as such. 
HTTPProtocolFactory = server.Site(resource)

# allows us to access the debian documentation in /usr/share/doc
# as a relative path
resource.putChild('doc', static.File('/usr/share/doc'))

# allows me to view the twisted cvs documentation on my site
# (just to show how to add links to local resources, consider this an
# example as you'd have to make this point to an actual directory
# on your computer. this also shows the very cool ability of twisted
# web to use python to aid in website configuration)
import os.path
from glob import glob

twDocPath = '/home/jonathan/divmod/Twisted/doc'
resource.putChild('tw-cvs-doc', static.File(twDocPath))

dirlist = glob(twDocPath + "/*")
for i, d in enumerate(dirlist):
    bname = os.path.basename(d)
    if bname == 'CVS':
        del dirlist[i]
    if not os.path.isdir(d):
        del dirlist[i]

for d in dirlist:
    b = os.path.basename(d)   
    resource.putChild('tw-cvs-doc/%s' % b, static.File(d))


# a resource that allows people to view the Woven Links tutorial
resource.putChild('woven-tut', static.File('/home/jonathan/public_html/phase2/tutorial'))

# an example of how to use util.Redirect()
# if a user requests /google, the server will redirect them too www.google.com
resource.putChild('google', util.Redirect('http://www.google.com'))

# let's add a cgi directory for man page lookups
resource.putChild('cgi-bin', twcgi.CGIDirectory('/usr/lib/cgi-bin'))

# create a new application with name 'HomePage'
application = service.Application('HomePage')

# create the actual tcp server that will listen on a socket
# and respond to requests
i = internet.TCPServer(7000, HTTPProtocolFactory)

# this attaches the application service to our tcp server's parent
i.setServiceParent(service.IServiceCollection(application))



