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
        --user <name>, -u:      set the username to <name>.
        --password <word>, -w:  set the password to <word>.
"""

class Options(usage.Options):
    optStrings = [["password", "w", "admin"],
                  ["user", "u", "admin"]]
    def opt_port(self, opt):
        try:
            self.portno = int(opt)
        except ValueError:
            raise usage.error("Invalid argument to 'port'!")
    opt_p = opt_port


def getPorts(app, config):
    
    bf = pb.BrokerFactory()
    bf.addService("twisted.manhole", service.Service({config.user: config.password}))
    try:
        portno = config.portno
    except AttributeError:
        portno = pb.portno
    return [(portno, bf)]
