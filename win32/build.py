import os.path, sys

from twisted.python.util import searchupwards
from twisted.python import usage
from distutils import sysconfig
import winreg

err=sys.stderr.write

class BuildOptions(usage.Options):
    optFlags=[["upload", "u", "Upload to sf.net using scp (requires an account with suitable permissions)"],
              ["help", 'h', "This help message"],
              ]
    optParameters=[["cyghome", "c", "",
                    "Path to the Cygwin root (as a native path, e.g. c:\cygwin)"],
                   ["twistedhome", "t", "",
                    "Path to the Twisted tree being built"],
                   ["netpbmbin", "n", "",
                    "Path to netpbm bin directory (containing pngtopnm)",]
                   ]

    def postOptions(self):
        if self['help']:
            err(str(self))
            sys.exit(2)

        successcheck=1
        if not self['cyghome']:
            self['cyghome']='**cygwin not found**'
            try:
                key=winreg.Key(winreg.HKLM,
                               r'SOFTWARE\Cygnus Solutions\Cygwin\mounts v2\/')
                self['cyghome']=key.values['native'].value
            except winreg.KeyNotFound:
                pass
        if not os.path.isdir(self['cyghome']):
            err('Cygwin must be installed!\n')
            successcheck=0

        self['pythonprefix']=sysconfig.get_config_var('prefix')

        staticpylib='%s/libs/libpython22.a' % self['pythonprefix']
        if not os.path.exists(staticpylib):
            err("libpython22.a must be present to build Twisted.\n" +
                "See http://sebsauvage.net/python/mingw.html\n")
            successcheck=0
            
        # try to find twisted in parents of the current directory first.
        # if that doesn't work, build whatever twisted is in the parents
        # of build.py itself
        if not self["twistedhome"]:
            home=searchupwards('.', ['setup.py'], ['twisted'])
            if not home:
                import build
                home=searchupwards(os.path.dirname(build.__file__),
                                   ['setup.py'], ['twisted'])
                if not home:
                    err("Run this script from the twisted source tree.  I need to find setup.py.\n")
                    successcheck=0
            self["twistedhome"]=home
        if not os.path.isdir(os.path.join(self["twistedhome"], "twisted")):
            err('%s does not contain a package named "twisted"\n' %
                self["twistedhome"])
            successcheck=0
        if not self['netpbmbin']:
            netpbmbin='%s/usr/local/netpbm/bin' % self['cyghome']
            self['netpbmbin']=netpbmbin
        if not os.path.isdir(netpbmbin):
            err('netpbm must be installed at %s.\n' % netpbmbin)
            successcheck=0
            
        # FIXME - check if distutils has --post-install
        if not successcheck:
            err('One or more parts of your build environment are not fully set up.  Cannot continue.\n')
            sys.exit(1)

def invoke(command, args):
    """Spawn the command, and exit with an error status if it fails"""
    argv=[command]+args.split()
    if not os.spawnve(os.P_WAIT, argv[0], argv, os.environ)==0:
        err("Subcommand failed: %s\n" % ' '.join(argv))
        raw_input('Press enter to quit...')
        sys.exit(1)

def run(argv=sys.argv):
    options=BuildOptions()
    try:
        options.parseOptions(argv[1:])
    except usage.UsageError, e:
        err(str(options))
        err(str(e))
        sys.exit(2)

    os.chdir(options["twistedhome"])

    # put home first in sys.path, we want to make sure the version
    # string matches the directory being built, not the directory
    # already installed
    sys.path.insert(0, options["twistedhome"])
    # delete our reference to twisted so the new import gets the version
    # of twisted located under home
    del sys.modules['twisted']
    from twisted.copyright import version

    twisteddist='Twisted-%s.win32-py2.2.exe' %  version
    twisteddistnodocs='Twisted%s-%s.win32-py2.2.exe' % ('NoDocs', version)

    shpath=os.environ['PATH']
    os.environ['PATH']='%s;%s' % (shpath,
                                  os.path.normpath(options['netpbmbin']))
    def python(args=''):
        invoke(r'%s\python.exe' % options['pythonprefix'], args)
    def scp(args=''):
        invoke(r'%s\bin\scp.exe' % options['cyghome'], args)
    def ssh(args=''):
        invoke(r'%s\bin\ssh.exe' % options['cyghome'], args)
    def sh(args=''):
        invoke(r'%s\bin\sh.exe' % options['cyghome'], args)
    def infozip(args=''):
        invoke(r'%s\bin\zip.exe' % options['cyghome'], args)

    # first run - no docs
    try:
        os.unlink('dist/%s' % twisteddist)
        os.unlink('dist/%s' % twisteddistnodocs)
    except EnvironmentError:
        pass
    try:
        os.unlink('doc/win32doc.zip')
    except EnvironmentError:
        pass
    python('setup.py clean -q --all')
    python('setup.py build -q --compiler=mingw32')
    python('setup.py bdist_wininst -q --install-script=twisted_postinstall.py')
    os.rename('dist/%s' % twisteddist, 'dist/%s' % twisteddistnodocs)

    # second run - docs, please
    sh('admin/process-docs')
    python('admin/epyrun -o doc/api')
    os.chdir('doc')
    infozip('-rq win32doc.zip examples/ -x "*CVS*" "*.cvsignore*"')
    infozip('-q win32doc.zip howto/*.xhtml howto/stylesheet.css howto/*.pdf')
    infozip('-q win32doc.zip specifications/*.xhtml')
    infozip('-q win32doc.zip img/*.png img/*.bmp')
    infozip('-q win32doc.zip vision/*.xhtml')
    infozip('-rq win32doc.zip api/ -x "*CVS*" "*.cvsignore" "*README"')
    os.chdir('..')
    python('setup.py bdist_wininst -q --install-script=twisted_postinstall.py')
    if options['upload']:
        scp('dist/%s dist/%s shell.sf.net:/home/groups/t/tw/twisted/htdocs' %
            (twisteddistnodocs, twisteddist))
        ssh('shell.sf.net chmod g+rw /home/groups/t/tw/twisted/htdocs/%s' %
            (twisteddistnodocs, twisteddist))
    
    raw_input('Done!\n')
    

if __name__=='__main__':
    run()
