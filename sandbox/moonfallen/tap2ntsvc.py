#!python
"""Create installable Windows packages using Twisted as an NT Service"""

import sys
import os.path
import ConfigParser
import re
import shutil

from twisted.python import usage, util
from twisted.application.app import reactorTypes
from twisted.persisted.sob import guessType

cftypes=('python', 'xml', 'source', 'pickle')

class Tap2NtsvcOptions(usage.Options):
    optParameters = [['type', 'y', None,
                      'Config file type out of: %s' % ', '.join(cftypes)],
                     ['output-file', 'o', None,
                      'Name of the setup executable produced'],
                     ['name', 'n', None,
                      'Short name of the service (used with "net start")'],
                     ['package_version', 'v', "1.0",
                      'Version string of your application'],
                     ['display_name', 'd', None,
                      'Human-readable name of the service'],
                     ['description', 'e', None,
                      'Longer description of the service'],
                     ['reactor', 'r', 'default',
                      "Which reactor to use out of: " + 
                      ", ".join(reactorTypes.keys())],
                     ['includes', 'i', "", """\
Comma-separated list of modules to bundle into the application
"""],
                     ['icon', 'c',
                      util.sibpath(__file__, 'pysvc.ico'),
                      "Windows icon file to use"],
                     ]

    def __init__(self):
        usage.Options.__init__(self)
        self.warnings = []
    
    def opt_type(self, cftype):
        if cftype not in cftypes:
            raise usage.UsageError("""\
Type must be one of [%s], not \"%s\"""" % (', '.join(cftypes),
                                           cftype))
        self['type'] = cftype

    def parseArgs(self, conffile):
        self['conffile'] = os.path.abspath(conffile)
        self['confbase'] = os.path.basename(conffile)
        try:
            guess = guessType(conffile)
        except KeyError:
            guess = None
        self['type'] = (self['type'] or guess or 'pickle')

    def getSynopsis(self):
        return "Usage: %s [options] <filename>" % __file__

    def postOptions(self):
        if not self['name']:
            self['name'] = os.path.splitext(self['confbase'])[0]
            
        if not isPythonName(self['name']):
            raise usage.UsageError("""\
\"%s\" was used for the name, but name must consist only of letters,
numbers and _.  (Use a different --name argument.)""" % self['name'])
        if not self['display_name']:
            self['display_name'] = "%s run by Twisted" % self['name']
        if not self['includes']:
            self.warnings.append("""\
--includes was not given. Most applications require at least one included \
module!""")


def isPythonName(st):
    m = re.match('[A-Za-z_][A-Za-z_0-9]*', st)
    if m:
        return m.end() == len(st)
    else:
        return 0


def ini2dict(configname, section):
    cp = ConfigParser.ConfigParser()
    cp.read(configname)
    dct = {}
    for name in cp.options(section):
        dct[name] = cp.get(section, name)
    return dct


def genFile(filename, template, options):
    try:
        outfile = file(filename, "w")
    except EnvironmentError:
        sys.exit("%s\n** Could not create file %s" %
                 (options.getSynopsis(), filename))
        
    outfile.write(template % options)
    outfile.close()


def run(argv = sys.argv):
    try:
        o = Tap2NtsvcOptions()
        o.parseOptions(argv[1:])
    except usage.UsageError, ue:
        sys.exit("%s\n** %s" % (o, ue))

    for w in o.warnings: print "--- WWW\nWarning: %s\n--- WWW" % w

    svc_appended = '%ssvc' % o['name']

    o['script'] = '%s.py' % svc_appended
    o['commandline'] = ' '.join(argv)
    o['dirname'] = svc_appended
    
    try:
        os.mkdir(svc_appended)
    except EnvironmentError, e:
        if e.strerror == 'File exists':
            pass
        else:
            sys.exit("\
Could not create directory %s because: %s" % (o['dirname'], e.strerr))
    print "Created directory %s" % o['dirname']
    os.chdir(o['dirname'])


    # generate the output files
    generated = {o['script'] : script_template,
                 'setup.py' : setup_template,
                 'setup.cfg' : cfg_template,
                 }
    for k in generated:
        genFile(k, generated[k], o)

    try:
        shutil.copy2(o['conffile'], '.')
    except EnvironmentError:
        if e.strerror == 'File exists':
            pass
        else:
            sys.exit("\
Could not copy file %s because: %s" % (o['conffile'], e.strerr))

    # invoke the packaging tools
    sys.path.insert(0, os.getcwd())
    import setup
    setup.run('setup.py py2exe'.split())


    import inno
    script = inno.Script(destination="{pf}\%s" % o['name'], **o)
    script.collect(os.path.join("dist", svc_appended))
    outname = '%s.iss' % o['name']
    out = file(outname, 'w+')
    script.writeScript(out)
    out.write(r'''[Run]
Filename: "{app}\%(svc)s.exe"; Parameters: "-install"
[UninstallRun]
Filename: "{sys}\net.exe"; Parameters: "%(name)s stop"
Filename: "{app}\%(svc)s.exe"; Parameters: "-remove"
''' % {'svc':svc_appended, 'name':o['name']})
    out.close()
    inno.build(outname)
    


    sys.stderr.write("%s: %d warnings.\n" % (os.path.basename(argv[0]),
                                             len(o.warnings)) )


setup_template = '''\
## This file was generated by tap2ntsvc, with the command line:
##   %(commandline)s

import sys
from distutils.core import setup
import py2exe

scriptfile = "%(script)s"
configfile = "%(confbase)s"
iconfile = "%(icon)s"

def run(argv = sys.argv):
    setup_args = {"scripts": [scriptfile],
                  "data_files": [("", [configfile]),
                                 ("", [iconfile]),
                                 ],
                  }
    orig_argv = sys.argv
    sys.argv = argv
    setup(**setup_args)
    sys.argv = orig_argv

if __name__ == "__main__":
    run()

'''

cfg_template = '''\
## This file was generated by tap2ntsvc, with the command line:
##   %(commandline)s
[py2exe]

service=%(name)s_ServiceControl
## prune docstrings (py2exe ignores them)
optimize=2
excludes=perfmon
# version_companyname =
# version_fileversion =
# version_legalcopyright =
# version_legaltrademarks =
version_productversion = %(package_version)s
icon = %(icon)s
version_filedescription = %(description)s
version_productname = %(display_name)s
includes = %(includes)s
'''

script_template = '''\
## This file was generated by tap2ntsvc, with the command line:
##   %(commandline)s

import os.path
import win32serviceutil, win32service

configfile = "%(confbase)s"
cftype = "%(type)s"
svcname = "%(name)s"
display = "%(display_name)s"
reactortype = "%(reactor)s"




class %(name)s_ServiceControl(win32serviceutil.ServiceFramework):

    _svc_name_ = svcname
    _svc_display_name_ = display

    def SvcDoRun(self):
        from twisted.application import app
        app.installReactor(reactortype)
        
        from twisted.application import service
        from twisted.python import util, log
        
        logfile = file("%%s.log" %% svcname, "a")
        log.startLogging(logfile)
        
        log.msg("Loading application from %%s" %% configfile)
        
        %(name)s_app = service.loadApplication(configfile, cftype)



        from twisted.internet import reactor

        app.startApplication(%(name)s_app, 1)
        reactor.run(installSignalHandlers=0)


    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        from twisted.internet import reactor
        reactor.stop()


if __name__ == \'__main__\':
    win32serviceutil.HandleCommandLine(%(name)s_ServiceControl)
'''
