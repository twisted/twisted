# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

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

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    zsh_mutuallyExclusive = [("file", "python", "xml", "source")]
    zsh_actions = {"file":'_files -g "*.tap"',
                   "python":'_files -g "*.py"', 
                   "xml":'_files -g "*.tax"', 
                   "source":'_files -g "*.tas"',}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}

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

