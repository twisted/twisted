
from recvline import RecvLineHandler

from twisted.application import service, internet

application = service.Application("Insults RecvLine Demo")

from demolib import makeService
makeService({'handler': RecvLineHandler,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
