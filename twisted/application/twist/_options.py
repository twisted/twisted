# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Command line options for C{twist}.
"""

from sys import stdout, stderr
from os import isatty
from textwrap import dedent

from twisted.copyright import version
from twisted.python.usage import Options
from twisted.logger import (
    LogLevel, InvalidLogLevelError,
    textFileLogObserver, jsonFileLogObserver,
)
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
        self["logLevel"] = self.defaultLogLevel
        self["logFile"] = stdout


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
        options=", ".join(
            '"{}"'.format(rt.shortName) for rt in getReactorTypes()
        ),
    )


    def installReactor(self):
        """
        Install the reactor.
        """
        name = self["reactorName"]
        try:
            self["reactor"] = installReactor(name)
        except NoSuchReactor:
            exit(ExitStatus.EX_CONFIG, "Unknown reactor: {}".format(name))


    def opt_log_level(self, levelName):
        """
        Set default log level.
        (options: {options}; default: "{default}")
        """
        try:
            self["logLevel"] = LogLevel.levelWithName(levelName)
        except InvalidLogLevelError:
            exit(
                ExitStatus.EX_CONFIG,
                "Invalid log level: {}".format(levelName)
            )

    opt_log_level.__doc__ = dedent(opt_log_level.__doc__).format(
        options=", ".join(
            '"{}"'.format(l.name) for l in LogLevel.iterconstants()
        ),
        default=defaultLogLevel.name,
    )


    def opt_log_file(self, fileName):
        """
        Log to file. ("-" for stdout, "+" for stderr; default: "-")
        """
        if fileName == "-":
            self["logFile"] = stdout
            return

        if fileName == "+":
            self["logFile"] = stderr
            return

        try:
            self["logFile"] = open(fileName, "a")
        except EnvironmentError as e:
            exit(
                ExitStatus.EX_CANTCREAT,
                "Unable to open log file {!r}: {}".format(fileName, e)
            )


    def opt_log_format(self, format):
        """
        Log file format.
        (options: "text", "json"; default: "text" if the log file is a tty,
        otherwise "json")
        """
        format = format.lower()

        if format == "text":
            self["fileLogObserverFactory"] = textFileLogObserver
        elif format == "json":
            self["fileLogObserverFactory"] = jsonFileLogObserver
        else:
            exit(
                ExitStatus.EX_CONFIG,
                "Invalid log format: {}".format(format)
            )
        self["logFormat"] = format

    opt_log_format.__doc__ = dedent(opt_log_format.__doc__)


    def selectDefaultLogObserver(self):
        """
        Set the L{fileLogObserverFactory} to the default appropriate for the
        chosen L{logFile}.
        """
        if "fileLogObserverFactory" not in self:
            logFile = self["logFile"]

            if hasattr(logFile, "fileno") and isatty(logFile.fileno()):
                self["fileLogObserverFactory"] = textFileLogObserver
            else:
                self["fileLogObserverFactory"] = jsonFileLogObserver


    def parseArgs(self):
        try:
            self.installReactor()
            self.selectDefaultLogObserver()
        except Exception as e:
            exit(
                ExitStatus.EX_SOFTWARE,
                "Unexpected error parsing arguments: {}".format(e)
            )

        Options.parseArgs(self)
