
from twisted.application import service
application = service.Application("Interactive Python Interpreter")

from demolib import makeService
from manhole import ColoredManhole

makeService({'protocolFactory': ColoredManhole,
             'protocolArgs': (None,),
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
