"""
I am the support module for making a telnet server with mktap.
"""

from twisted.protocols import telnet
from twisted.internet import tcp
from twisted.python import usage
import sys


usage_message = """
usage: mktap telnet [OPTIONS]

Options are as follows:
        --port <#>, -p:         set the port number to <#>.
	--username <name>, -u:  set the username to <name>
	--password <pword>, -w: set the password to <pword>
"""

class Options(usage.Options):
    optStrings = [["username", "u", "admin"],
		  ["password", "w", "changeme"]]
    def opt_port(self, opt):
        try:
	    self.portno = int(opt)
	except ValueError:
	    raise usage.error("Invalid argument to 'port'!")
    opt_p = opt_port

def getPorts(app, config):
    t = telnet.ShellFactory()
    t.username = config.username
    t.password = config.password
    try:
        portno = config.portno
    except AttributeError:
        portno = 4040
    return [(portno, t)]
