# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
from twisted.python import usage
from twisted.application import app
from twisted.persisted import sob
import sys, getpass

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
