"""Build service executables to launch Twisted application .tac files.
"""
import sys, os
import tempfile
import atexit
import itertools
import shutil
import ConfigParser

from py2exe.build_exe import py2exe as build_exe
import py2exe

from find_modules import find_modules

from ntsvc.helpers import helpers

class TwistedAppDistribution(py2exe.Distribution):
    """Parse the 'appconfig' option, setting the 'service' and 'data_files'
    attrs based on the filename.  
    If ntsvc.cfg already exists, use those values to configure myself instead
    of 'appconfig'.
    """
    def __init__(self, attrs):
        if os.path.isfile('ntsvc.cfg'):
            attrs.pop('appconfig', 'DONTCARE') # eliminates a distutils warning
            cp = ConfigParser.ConfigParser()
            cp.read('ntsvc.cfg')
            self.twisted = dict(cp.items('service'))
            config = self.twisted['basecf']
            short_name = self.twisted['svcname']
        else:
            config = attrs.pop('appconfig', '//missing option appconfig//')
            short_name = os.path.splitext(os.path.basename(config))[0]
            self.twisted = dict(svcname=short_name, 
                                display=short_name, 
                                reactortype='default',
                                cftype='python',
                                basecf=config)
        if os.path.dirname(self.twisted['basecf']) != '':
            raise ValueError("Directory names not allowed for "
                             "the application file: %s" % 
                                   (self.twisted['basecf'],))
        attrs['service'] = [{'modules': ['ntsvc.runner'], 
                             'dest_base': '%sctl' % (short_name,),
                             }]
        attrs.setdefault('data_files', []).append(
                ('', [config, 'ntsvc.cfg'])
                         )

        py2exe.Distribution.__init__(self, attrs)

class twistedservice(build_exe):
    """Generate a script from boilerplate that will start the service.
    Read the tac file with modulegraph and build a list of files to include.
    Pass that list along to py2exe's modulefinder.
    """
    def run(self):
        """add tac-imported modules into self.includes"""
        twcfg = self.distribution.twisted

        # create ntsvc.cfg from twcfg's values if it is missing
        if not os.path.isfile('ntsvc.cfg'):
            cp = ConfigParser.ConfigParser()
            cp.add_section('service')
            for o, v in twcfg.items():
                cp.set('service', o, v)
            cp.write(file('ntsvc.cfg', 'w'))

        # find modules imported via the .tac, include them
        print "I: finding modules imported by %(basecf)s" % twcfg
        mf = find_modules(scripts=[twcfg['basecf']])

        # Add modules that the normal module finding mechanism won't
        # follow; mostly, these will be imports from strings such as what's
        # done by Nevow.  This is a plugin system.  Add to helpers.helpers
        # if you want your own default module injecting.
        for imported, injected in helpers.items():
            m = mf.findNode(imported)
            if m is not None and m.filename is not None:
                for module, attrs in injected:
                    mf.import_hook(module, m, attrs)
        
        config = os.path.abspath(twcfg['basecf'])
        isinteresting = lambda m: interestingModule(m, config)
        li = list(itertools.ifilter(isinteresting, mf.flatten()))
        
        self.includes.extend([node.identifier for node in li])
        return build_exe.run(self)

def interestingModule(mfnode, scriptpath):
    """See if an mfnode is interesting; that is:
    * not builtin
    * not excluded
    * not the input script
    """
    return mfnode.filename is not None and mfnode.filename != scriptpath

