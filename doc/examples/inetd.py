# twistd -y me

from twisted.internet import app
from twisted.inetd import tap

application = app.Application('tinetd')
options = tap.Options()
tap.updateApplications(application, options)
