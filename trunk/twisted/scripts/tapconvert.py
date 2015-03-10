# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, getpass

from twisted.python import usage
from twisted.application import app
from twisted.persisted import sob


class ConvertOptions(usage.Options):
    synopsis = "Usage: tapconvert [options]"
    optParameters = [
        ['in',      'i', None,     "The filename of the tap to read from"],
        ['out',     'o', None,     "A filename to write the tap to"],
        ['typein',  'f', 'guess',
         "The  format to use; this can be 'guess', 'python', "
         "'pickle', 'xml', or 'source'."],
        ['typeout', 't', 'source',
         "The output format to use; this can be 'pickle', 'xml', or 'source'."],
        ]

    optFlags = [
        ['decrypt', 'd', "The specified tap/aos/xml file is encrypted."],
        ['encrypt', 'e', "Encrypt file before writing"]
        ]

    compData = usage.Completions(
        optActions={"typein": usage.CompleteList(["guess", "python", "pickle",
                                                  "xml", "source"]),
                    "typeout": usage.CompleteList(["pickle", "xml", "source"]),
                    "in": usage.CompleteFiles(descr="tap file to read from"),
                    "out": usage.CompleteFiles(descr="tap file to write to"),
                    }
        )

    def postOptions(self):
        if self['in'] is None:
            raise usage.UsageError("%s\nYou must specify the input filename."
                                   % self)
        if self["typein"] == "guess":
            try:
                self["typein"] = sob.guessType(self["in"])
            except KeyError:
                raise usage.UsageError("Could not guess type for '%s'" %
                                       self["typein"])

def run():
    options = ConvertOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, e:
        print e
    else:
        app.convertStyle(options["in"], options["typein"],
                     options.opts['decrypt'] or getpass.getpass('Passphrase: '),
                     options["out"], options['typeout'], options["encrypt"])
