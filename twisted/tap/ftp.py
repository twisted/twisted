"""
I am the support module for making a ftp server with mktap.
"""

from twisted.protocols import ftp2
from twisted.internet import tcp
from twisted.python import usage
import sys


usage_message = """
usage: mktap ftp [OPTIONS]

Options are as follows:
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
    t = ftp.ShellFactory()
    try:
        portno = config.portno
    except AttributeError:
        portno = 2121
    return [(portno, t)]
