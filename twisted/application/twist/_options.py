# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Command line options for C{twist}.
"""

from sys import stdout

from operator import attrgetter

from twisted.python.usage import Options
from ..reactors import installReactor, NoSuchReactor, getReactorTypes
from ..runner import exit, ExitStatus



class TwistOptions(Options):
    """
    Command line options for C{twist}.
    """

    def __init__(self):
        Options.__init__(self)

        self["reactorName"] = "default"


    def opt_reactor(self, name):
        """
        The name of the reactor to use.
        """
        self["reactorName"] = name


    def opt_list_reactors(self):
        """
        List available reactors.
        """
        reactorTypes = sorted(getReactorTypes(), key=attrgetter("shortName"))
        stdout.write("Available reactors:\n")
        for reactorType in reactorTypes:
            stdout.write(
                "    {rt.shortName:10} {rt.description}\n"
                .format(rt=reactorType)
            )
        exit(ExitStatus.EX_OK)


    def installReactor(self):
        name = self["reactorName"]
        try:
            self["reactor"] = installReactor(name)
        except NoSuchReactor:
            exit(ExitStatus.EX_CONFIG, "Unknown reactor: {}".format(name))


    def parseArgs(self):
        self.installReactor()

        Options.parseArgs(self)
