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

from twisted.python import log, usage, util
from twisted.persisted import styles

# System imports
import os, sys
from cPickle import load
from cStringIO import StringIO

mainMod = sys.modules['__main__']

# Functions from twistd/mktap

class EverythingEphemeral(styles.Ephemeral):
    def __getattr__(self, key):
        try:
            return getattr(mainMod, key)
        except AttributeError:
            if initRun:
                raise
            else:
                log.msg("Warning!  Loading from __main__: %s" % key)
                return styles.Ephemeral()

#

class LoaderCommon:
    """Simple logic for loading persisted data"""
    loadmessage = "Loading %s..."
    def __init__(self, filename, encrypted=None, passphrase=None):
        self.filename = filename
        self.encrypted = encrypted
        self.passphrase = passphrase

    def load(self):
        "Returns the application"
        log.msg(self.loadmessage % self.filename)
        if self.encrypted:
            self.data = open(self.filename, 'r').read()
            self.decrypt()
        else:
            self.read()
        return self.decode()       
        
    def read(self, filename):
        pass

    def decrypt(self):
        try:
            from Crypto.Cipher import AES
            self.data = AES.new(self.passphrase).decrypt(self.data)
        except ImportError:
            print "The --decrypt flag requires the PyCrypto module, no file written."
            
    def decode(self):
        pass

class LoaderXML(LoaderCommon):
    loadmessage = '<Loading file="%s" />' 
    def read(self, filename):
        self.data = open(filename, 'r').read()
    def decode(self):
        from twisted.persisted.marmalade import unjellyFromXML
        sys.modules['__main__'] = EverythingEphemeral()
        application = unjellyFromXML(StringIO(self.data))
        sys.modules['__main__'] = mainMod
        styles.doUpgrade()
        return application

class LoaderPython(LoaderCommon):
    def decrypt(self):
        log.msg("Python files are never encrypted")
    
    def decode(self):
        pyfile = os.path.abspath(self.filename)
        d = {'__file__': self.filename}
        execfile(pyfile, dict, dict)
        try:
            application = dict['application']
        except KeyError:
            log.msg("Error - python file %s must set a variable named 'application', an instance of twisted.internet.app.Application. No such variable was found!" % repr(self.filename))
            sys.exit()
        return application

class LoaderSource(LoaderCommon):
    def read(self):
        self.data = open(self.filename, 'r').read()

    def decode(self):
        from twisted.persisted.aot import unjellyFromSource
        sys.modules['__main__'] = EverythingEphemeral()
        application = unjellyFromSource(StringIO(self.data))
        application.persistStyle = "aot"
        sys.modules['__main__'] = mainMod
        styles.doUpgrade()
        return application

class LoaderTap(LoaderCommon):
    def read(self):
        self.data = open(self.filename, 'rb').read()

    def decode(self):
        sys.modules['__main__'] = EverythingEphemeral()
        application = load(StringIO(self.data))
        sys.modules['__main__'] = mainMod
        styles.doUpgrade()
        return application

loaders = {'python': LoaderPython,
           'xml': LoaderXML,
           'source': LoaderSource,
           'pickle': LoaderTap}

def loadPersisted(filename, kind, encrypted, passphrase):
    "Loads filename, of the specified kind and returns an application"
    Loader = loaders[kind]
    l = Loader(filename, encrypted, passphrase)
    application = l.load()
    return application

def savePersisted(app, filename, encrypted):
    if encrypted:
        try:
            import Crypto
            app.save(filename=filename, passphrase=util.getPassword("Encryption passphrase: "))
        except ImportError:
            print "The --encrypt flag requires the PyCrypto module, no file written."
    else:
        app.save(filename=filename)

class ConvertOptions(usage.Options):
    synopsis = "Usage: tapconvert [options]"
    optParameters = [
        ['in',      'i', None,     "The filename of the tap to read from"],
        ['out',     'o', None,     "A filename to write the tap to"],
        ['typein',  'f', 'guess',  "The  format to use; this can be 'guess', 'python', 'pickle', 'xml', or 'source'."],
        ['typeout', 't', 'source', "The output format to use; this can be 'pickle', 'xml', or 'source'."],
        ['decrypt', 'd', None,     "The specified tap/aos/xml file is encrypted."],
        ['encrypt', 'e', None,     "Encrypt file before writing"]]
    
    
    def postOptions(self):
        if self['in'] is None:
            raise usage.UsageError("You must specify the input filename.")


def run():
    options = ConvertOptions()
    options.parseOptions(sys.argv[1:])

    passphrase = None
    if options.opts['decrypt']:
        import getpass
        passphrase = getpass.getpass('Passphrase: ')

    if options["typein"] == "guess":
        if options["in"][-3:] == '.py':
            options["typein"] = 'python'
        else:
            try:
                options["typein"] = ({ '.tap': 'pickle',
                                       '.tas': 'source',
                                       '.tax': 'xml' }[options["in"][-4:]])
            except KeyError:
                print "Error: Could not guess the type."
                return

    if None in [options['in']]:
        options.opt_help()
    a = loadPersisted(options["in"], options["typein"], options["decrypt"], passphrase)
    a.persistStyle = ({'xml': 'xml',
                       'source': 'aot', 
                       'pickle': 'pickle'}
                       [options["typeout"]])
    savePersisted(a, filename=options["out"], encrypted=options["encrypt"])
