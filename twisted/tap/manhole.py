"""
I am the support module for making a telnet server with mktap.
"""

from twisted.manhole import service
from twisted.spread import pb
from twisted.internet import tcp
from twisted.python import usage
import sys


usage_message = """Usage: mktap manhole [OPTIONS]

Options:
        --port <#>, -p:         set the port number to <#>.
"""

class Options(usage.Options):
    def opt_port(self, opt):
        try:
	    self.portno = int(opt)
	except ValueError:
	    raise usage.error("Invalid argument to 'port'!")
    opt_p = opt_port

def getPorts(app, config):
    bf = pb.BrokerFactory()
    bf.addService("manhole", service.Service())
    try:
        portno = config.portno
    except AttributeError:
        portno = pb.portno
    return [(portno, bf)]
