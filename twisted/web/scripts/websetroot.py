# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 
from twisted.scripts import twistd
from twisted.python import usage

try:
    import cPickle as pickle
except ImportError:
    import pickle

class Options(usage.Options):
    optFlags = [
                ['encrypted', 'e' ,
                 "The specified tap/aos/xml file is encrypted."]
               ]


    optParameters = [
                  ['port','p', 80,
                   "The port the web server is running on"],
                  ['file','f','twistd.tap',
                   "read the given .tap file"],
                  ['python','y', None,
                   "read an application from within a Python file"],
                  ['xml', 'x', None,
                   "Read an application from a .tax file (Marmalade format)."],
                  ['source', 's', None,
                   "Read an application from a .tas file (AOT format)."],
                    ]

    def opt_script(self, scriptname):
        """Set the root resource of the web server to the resource created 
        (and put into the `resource' variable) by this script."""
        d = {}
        execfile(scriptname, d)
        self['root'] = d['resource']

    def opt_pickle(self, picklename):
        """Set the root resource of the web server to the resource saved in 
        this pickle."""
        self['root'] = pickle.load(open(picklename))
 

def getFactory(app, port):
    for (num, fact, _, _) in app.tcpPorts:
        if num == port:
            return fact
    raise LookupError('no such port')

def main(config):
    if config['encrypted']:
        import getpass
        passphrase = getpass.getpass('Passphrase: ')
    else:
        passphrase = None
    application = twistd.loadApplication(config, passphrase)
    site = getFactory(application, int(config['port']))
    site.resource = config['root']
    application.save()


def run():
    import sys
    config = Options()
    config.parseOptions()
    try:
        main(config)
    except LookupError, err:
        sys.exit(sys.argv[0]+": "+str(err))
    except IOError, err:
        sys.exit(sys.argv[0]+": %s: %s" % (err.filename, err.strerror))

if __name__ == '__main__':
    run()

