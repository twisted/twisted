
import insults

from twisted.application import service

application = service.Application("Insults Demo App")

from demolib import makeService
from draw import Draw
makeService({'protocolFactory': Draw,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
