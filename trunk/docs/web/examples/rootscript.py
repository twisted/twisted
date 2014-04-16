# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is a Twisted Web Server with Named-Based Virtual Host Support.

Usage:
    $ sudo twistd -ny rootscript.py

Note: You need to edit your hosts file for this example
to work. Need to add the following entry:

    127.0.0.1   example.com

Then visit http://example.com/ with a web browser and compare the results to
visiting http://localhost/.
"""

from twisted.web import vhost, static, script, server
from twisted.application import internet, service

default = static.Data('text/html', '')
# Setting up vhost resource.
default.putChild('vhost', vhost.VHostMonsterResource())
resource = vhost.NameVirtualHost()
resource.default = default
# Here we use /var/www/html/ as our root diretory for the web server, you can
# change it to whatever directory you want.
root = static.File("/var/www/html/")
root.processors = {'.rpy': script.ResourceScript}
# addHost binds domain name example.com to our root resource.
resource.addHost("example.com", root)

# Setup Twisted Application.
site = server.Site(resource)
application = service.Application('vhost')
sc = service.IServiceCollection(application)
# Only the processes owned by the root user can listen @ port 80, change the
# port number here if you don't want to run it as root.
i = internet.TCPServer(80, site)
i.setServiceParent(sc)
