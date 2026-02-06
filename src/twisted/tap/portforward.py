# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support module for making a port forwarder with twistd.
"""
from twisted.application import strports
from twisted.protocols import portforward
from twisted.python import usage


class Options(usage.Options):
    synopsis = "[options]"
    longdesc = "(Deprecated) Port Forwarder. See 'twist forward' instead."
    optParameters = [
        ["port", "p", "tcp:6666", "The string endpoint to listen on."],
        ["host", "h", "localhost", "The destination host to connect to."],
        ["dest_port", "d", 6665, "Set the destination port to connect to."],
    ]

    compData = usage.Completions(optActions={"host": usage.CompleteHostnames()})


def makeService(config):
    """
    Create a port-forwarding service.
    """
    f = portforward.ProxyFactory(config["host"], int(config["dest_port"]))
    return strports.service(config["port"], f)
