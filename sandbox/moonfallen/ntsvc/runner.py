import sys
import os.path
import ConfigParser

import warnings; warnings.filterwarnings('ignore') # FIXME

import win32serviceutil, win32service

from twisted.python import util

# for py2exe, ntsvcmaker, etc.
try:
    if not os.path.isfile(__file__):
        raise NameError(__file__)
except NameError:
    __file__ = sys.executable
 

def searchlikely(filename):
    """Determine if filename can be accessed either as a sibling of __file__
    or by itself.  Raise an EnvironmentError if it exists but is unreadable.
    Raise the default error if it is simply missing.
    """
    unreadable = []
    for fn in [util.sibpath(__file__, filename), filename]:
        if os.path.isfile(fn):
            if os.access(fn, os.R_OK):
                return fn
            else:
                unreadable.append('%s exists but is not readable.' % (fn,))
    if len(unreadable) > 0:
        raise EnvironmentError(' '.join(unreadable))

    # raise a missing file exception
    file(filename, 'r').close()

# read the name of the tac, etc. from an ini file
cp = ConfigParser.ConfigParser()
cp.read(searchlikely("ntsvc.cfg"))
config = dict(cp.items('service'))

def run():
    from twisted.application import app
    app.installReactor(config['reactortype'])
    
    from twisted.application import service
    from twisted.python import util, log

    # look for a readable config file
    cf = searchlikely(config['basecf'])

    logname = util.sibpath(cf, "%s.log" % config['svcname'])
    logfile = file(logname, "a")
    log.startLogging(logfile)

    log.msg("Loading application from %s" % cf)
    
    application = service.loadApplication(cf, config['cftype'])



    from twisted.internet import reactor

    app.startApplication(application, 1)
    reactor.run(installSignalHandlers=0)


class ServiceControl(win32serviceutil.ServiceFramework):

    _svc_name_ = config['svcname']
    _svc_display_name_ = config['display']

    def SvcDoRun(self):
        run()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        from twisted.internet import reactor
        reactor.stop()


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(ServiceControl)
# run() # FIXME
