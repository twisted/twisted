import sys, os
import tempfile
import atexit
import itertools
import shutil

from py2exe.build_exe import py2exe as build_exe
import py2exe

from find_modules import find_modules

from ntsvc.helpers import helpers

servicectl_template = '''\
import sys, os

import warnings; warnings.filterwarnings('ignore') # FIXME

import win32serviceutil, win32service

basecf = "%(confbase)s"
cftype = "python"
svcname = "%(name)s"
display = "%(display_name)s"
reactortype = "%(reactor)s"

try:
    __file__
except NameError:
    __file__ = sys.executable


def run():
    from twisted.application import app
    app.installReactor(reactortype)
    
    from twisted.application import service
    from twisted.python import util, log

    # look for a readable config file
    for cf in (util.sibpath(sys.executable, basecf),
               util.sibpath(__file__, basecf),
               basecf):
        try:
            file(cf, \'r\').close()
        except EnvironmentError:
            continue
        else:
            break

    logname = util.sibpath(cf, "%%s.log" %% svcname)
    logfile = file(logname, "a")
    log.startLogging(logfile)

    log.msg("Loading application from %%s" %% cf)
    
    %(name)s_app = service.loadApplication(cf, cftype)



    from twisted.internet import reactor

    app.startApplication(%(name)s_app, 1)
    reactor.run(installSignalHandlers=0)


class %(name)s_ServiceControl(win32serviceutil.ServiceFramework):

    _svc_name_ = svcname
    _svc_display_name_ = display

    def SvcDoRun(self):
        run()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        from twisted.internet import reactor
        reactor.callFromThread(reactor.stop)


if __name__ == \'__main__\':
    win32serviceutil.HandleCommandLine(%(name)s_ServiceControl)
# run() # FIXME
'''


class TwistedAppDistribution(py2exe.Distribution):
    """Parse the 'appconfig' option, setting the 'service' and 'data_files'
    attrs based on the filename.  The actual script named as 'service' will be
    generated later, by twistedservice.run()
    """
    def __init__(self, attrs):
        config = attrs.pop('appconfig', 'missing/option/appconfig')
        short_name = os.path.splitext(os.path.basename(config))[0]
        self.twisted = dict(name=short_name, display_name=short_name, 
                            reactor='default', confbase=config)
        attrs['service'] = ['%(name)sctl' % self.twisted]
        attrs.setdefault('data_files', []).append(('', [config]))

        py2exe.Distribution.__init__(self, attrs)

class twistedservice(build_exe):
    """Generate a script from boilerplate that will start the service.
    Read the tac file with modulegraph and build a list of files to include.
    Pass that list along to py2exe's modulefinder.
    """
    def run(self):
        """add tac-imported modules into self.includes"""
        twisted = self.distribution.twisted

        # create a directory and arrange for its cleanup later
        svcdir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, svcdir)

        svcfile = '%(name)sctl.py' % twisted
        
        # self.distribution.console = [os.path.join(svcdir, svcfile)] # FIXME

        tf = file(os.path.join(svcdir, svcfile), 'w')
        tf.write(servicectl_template % twisted)
        tf.close()

        # add $TEMPDIR to sys.path so the generated file will be importable
        sys.path.insert(0, svcdir)

        # find modules imported via the .tac, include them
        print "I: finding modules imported by %(confbase)s" % twisted
        mf = find_modules(scripts=[twisted['confbase']])

        # Add modules that the normal module finding mechanism won't
        # follow; mostly, this is imports from strings such as what's
        # done by Nevow.  This is a plugin system.  Add to helpers.helpers
        # if you want your own default module injecting.
        for imported, injected in helpers.items():
            m = mf.findNode(imported)
            if m is not None and m.filename is not None:
                for module, attrs in injected:
                    mf.import_hook(module, m, attrs)
        
        config = os.path.abspath(twisted['confbase'])
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

