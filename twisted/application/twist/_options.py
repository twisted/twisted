# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Command line options for C{twist}.
"""

from operator import attrgetter

from twisted.copyright import version
from twisted.python.usage import Options
from twisted.python.filepath import FilePath
from ..reactors import installReactor, NoSuchReactor, getReactorTypes
from ..runner import exit, ExitStatus



class TwistOptions(Options):
    """
    Command line options for C{twist}.
    """

    def __init__(self):
        Options.__init__(self)

        self["reactorName"] = "default"


    def opt_version(self):
        """
        Print version and exit.
        """
        exit(ExitStatus.EX_OK, "{}".format(version))


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

        info = ["Available reactors:"]

        for reactorType in reactorTypes:
            info.append(
                "    {rt.shortName:10} {rt.description}"
                .format(rt=reactorType)
            )
        exit(ExitStatus.EX_OK, "\n".join(info))


    def installReactor(self):
        name = self["reactorName"]
        try:
            self["reactor"] = installReactor(name)
        except NoSuchReactor:
            exit(ExitStatus.EX_CONFIG, "Unknown reactor: {}".format(name))


    def opt_pidfile(self, path):
        """
        The path to the PID file.
        """
        self["pidFilePath"] = FilePath(path)


    def parseArgs(self):
        self.installReactor()

        Options.parseArgs(self)
