"""
I am a support module for making TOC servers with mktap.
"""

usage_message = """
usage: mktap toc [-p <port>]
"""

from twisted.protocols import toc 
from twisted.internet import tcp
from twisted.python import usage
import sys

class Options(usage.Options):
    optStrings = [["port", "p", 5190]]


def getPorts(app, config):
    t = toc.TOCFactory()
    portno = int(config.port)
    return [(portno, t)]
