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

# sort out what __file__ really is so py2exe can work
if not os.path.isfile(__file__):
    __file__ = sys.executable
default_icon = util.sibpath(__file__, "pysvc.ico")

cftypes=('python', 'xml', 'source', 'pickle')

class Tap2NtsvcOptions(usage.Options):
    optParameters = [['type', 'y', None,
                      'Config file type out of: %s' % ', '.join(cftypes)],
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
                     ['icon', 'c', default_icon,
                      "Windows icon file to use"],
                     ]
    optFlags = [['skip-py2exe', None,
                 "Don't do py2exe build step (implies --skip-inno-script)"],
                ['skip-inno-script', None,
                 "Don't do .iss script generation step (implies --skip-inno)"],
                ['skip-inno', None,
                 "Don't do Inno compile step"],
                ]

    def __init__(self):
        usage.Options.__init__(self)
        self.warnings = []

    def opt_skip_py2exe(self):
        self['skip-py2exe'] = 1
        self.opt_skip_inno_script()

    def opt_skip_inno_script(self):
        self['skip-inno-script'] = 1
        self['skip-inno'] = 1
    
    def opt_type(self, cftype):
        if cftype not in cftypes:
            raise usage.UsageError("""\
Type must be one of [%s], not \"%s\"""" % (', '.join(cftypes),
                                           cftype))
        self['type'] = cftype

    opt_y = opt_type

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
    o['options-repr'] = repr(o)
    
    try:
        os.mkdir(svc_appended)
        print "Created directory %s" % o['dirname']
    except EnvironmentError, e:
        if e.strerror == 'File exists':
            pass
        else:
            sys.exit("\
Could not create directory %s because: %s" % (o['dirname'], e.strerr))
    os.chdir(o['dirname'])


    # generate the output files
    generated = {o['script'] : servicectl_template,
                 'setup.py' : setup_template,
                 'setup.cfg' : cfg_template,
                 'README.txt' : readme_template,
                 'do_inno_script.py' : do_inno_script_template,
                 'do_inno.py' : do_inno_template,
                 'Makefile' : makefile_template,
                 }
    for k in generated:
        genFile(k, generated[k], o)

    try:
        shutil.copy2(o['conffile'], '.')
    except EnvironmentError, e:
        if e.strerror == 'File exists':
            pass
        else:
            sys.exit("\
Could not copy file %s because: %s" % (o['conffile'], e.strerror))

    # invoke the packaging tools
    if not o['skip-py2exe']:
        sys.path.insert(0, util.sibpath(o['conffile'], ''))
        sys.path.insert(0, os.getcwd())
        import setup
        setup.run('setup.py -q py2exe'.split())

        if not o['skip-inno-script']:
            execfile("do_inno_script.py")

            if not o['skip-inno']:
                execfile("do_inno.py")
                final = os.path.abspath("%s\\%s-setup-%s.exe" %
                                        (svc_appended,
                                        o['name'],
                                        o['package_version']))
                print "Output written to %s" % final

    sys.stderr.write("%s: %d warnings.\n" %
                     (os.path.basename(argv[0]), len(o.warnings)))

setup_template = '''\
## This file was generated by tap2ntsvc, with the command line:
##   %(commandline)s

import sys
from distutils.core import setup
import py2exe

scriptfile = "%(script)s"
configfile = "%(confbase)s"

def run(argv = sys.argv):
    setup_args = {"scripts": [scriptfile],
                  "data_files": [("", [configfile]),
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

servicectl_template = '''\
## This file was generated by tap2ntsvc, with the command line:
##   %(commandline)s

import sys
import os.path
import re

import win32serviceutil, win32service

basecf = "%(confbase)s"
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


    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        from twisted.internet import reactor
        reactor.callFromThread(reactor.stop)


if __name__ == \'__main__\':
    win32serviceutil.HandleCommandLine(%(name)s_ServiceControl)
'''

do_inno_script_template = r'''
import inno
import os.path

options = %(options-repr)s
filemapper = "%(name)s.fms"

scr = inno.Script(**options)

# write an fmlang script so future runs will operate on the (possibly
# user-edited) commands list, and not a static list of files
if not os.path.isfile(filemapper):
    scr.collect(os.path.join("dist", "%(name)ssvc"))
    file(filemapper, "w").write(scr.fmscript)
    print "Created %%s" %% filemapper
else:
    scr.fmscript = file(filemapper).read()
    print "Loaded %%s" %% filemapper
    scr.runFileCommands()

outname = "%(name)s.iss"
out = file(outname, "w+")
scr.writeScript(out)
out.write(r"""[Run]
Filename: "{app}\%(name)ssvc.exe"; Parameters: "-remove"; StatusMsg: "Installing %(name)s service"
Filename: "{app}\%(name)ssvc.exe"; Parameters: "-install"; StatusMsg: "Installing %(name)s service"
[UninstallRun]
Filename: "{sys}\net.exe"; Parameters: "%(name)s stop"
Filename: "{app}\%(name)ssvc.exe"; Parameters: "-remove"
""")
out.close()
'''

do_inno_template = '''from inno import build; build("%(name)s.iss")\n'''

readme_template = '''\
This directory contains files created by:
  %(commandline)s

______________

MAKING CHANGES
______________

Files in here that you are likely to modify: setup.cfg, %(name)s.fms and
%(name)s.iss.

-- Missing Imports --
If you get errors in the Application log that say you are missing imports,
edit setup.cfg, and add the named module to the line "includes=".  You can add
multiple modules here, separated by commas.  Then do:
   python setup.py py2exe; python do_inno_script.py; python do_inno.py

-- Missing Data Files --
If you need to distribute data files with your application, the easiest way to
add them is to edit %(name)s.fms.  This file uses a *very* simple language for
finding files.  Supported commands are:
  add [<glob>]
    grab all filenames (not names of directories) in this dir matching glob
  chdir (or cd) <dir>
    from now on, add all entries relative to this directory
  diradd [<glob>]
    add directories matching glob (not their contents--use for empty dirs)
  exclude <glob>
    from now on, don\'t grab any files that match this glob
  show
    print the current list of dest:source mappings to stdout
  unexclude <glob>
    stop excluding this glob, if it was previously excluded

"import inno.fmlang; help(inno.fmlang)" (in the Python interactive
interpreter) will describe fmlang in more detail.

After editing the file, you have two choices.  If you GNU Make (nmake
might also work):
    make
If not, run the commands by hand:
    python do_inno_script.py; python do_inno.py

-- Other Stuff --
You can do almost anything else you want with your distributable package by
editing %(name)s.iss directly.  There is a help file for Inno Setup scripts in
the inno/program directory of the Innoconda distribution.  After editing the
file, do:
   python do_inno.py   # (or make)
'''

makefile_template = '''\
# assumes Cygwin make and environment

name=%(name)s
version=%(package_version)s
target=$(name)-$(version)-setup.exe

all: $(target)
	@echo "Done"
	
$(target): $(name).iss do_inno.py
	python do_inno.py

$(name).iss: $(name).fms do_inno_script.py setup.py setup.cfg $(name).tap
	python setup.py py2exe
	python do_inno_script.py

clean:
	rm -rf dist build
	rm -f $(name).iss
	rm -f *.pyc
	rm -f $(target)
'''
