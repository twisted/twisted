#!python

from twisted.internet import main
from twisted.spread import pb

from twisted.web import widgets, server

import gadgets
import service

# Create Twisted application object
application = main.Application("posting board")

# Create the service
forumService = service.ForumService("posting", application, "localhost", 5432)

# Create posting board object
gdgt = gadgets.ForumGadget(application, forumService)

# Accept incoming connections!
application.listenOn(8485, server.Site(gdgt))

# Done.
