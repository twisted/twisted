# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Command line options for C{twist}.
"""

from textwrap import dedent

from twisted.copyright import version
from twisted.python.usage import Options
from twisted.logger import LogLevel, InvalidLogLevelError
from ..reactors import installReactor, NoSuchReactor, getReactorTypes
from ..runner import exit, ExitStatus



class TwistOptions(Options):
    """
    Command line options for C{twist}.
    """

    defaultLogLevel = LogLevel.info


    def __init__(self):
        Options.__init__(self)

        self["reactorName"] = "default"
        self["logLevel"]    = self.defaultLogLevel


    def opt_version(self):
        """
        Print version and exit.
        """
        exit(ExitStatus.EX_OK, "{}".format(version))


    def opt_reactor(self, name):
        """
        The name of the reactor to use.
        (options: {options})
        """
        self["reactorName"] = name

    opt_reactor.__doc__ = dedent(opt_reactor.__doc__).format(
        options=", ".join(rt.shortName for rt in getReactorTypes()),
    )


    def installReactor(self):
        name = self["reactorName"]
        try:
            self["reactor"] = installReactor(name)
        except NoSuchReactor:
            exit(ExitStatus.EX_CONFIG, "Unknown reactor: {}".format(name))


    def opt_log_level(self, levelName):
        """
        Set default log level.
        (options: {options}; default: {default})
        """
        try:
            self["logLevel"] = LogLevel.levelWithName(levelName)
        except InvalidLogLevelError:
            exit(
                ExitStatus.EX_USAGE,
                "Invalid log level: {}".format(levelName)
            )

    opt_log_level.__doc__ = dedent(opt_log_level.__doc__).format(
        options=", ".join(l.name for l in LogLevel.iterconstants()),
        default=defaultLogLevel.name,
    )


    def parseArgs(self):
        self.installReactor()

        Options.parseArgs(self)
