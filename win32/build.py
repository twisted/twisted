import os.path, sys

from twisted.python.util import searchupwards
from twisted.python import usage
from distutils import sysconfig
import winreg

err=sys.stderr.write

def quickdict(initial={}, *args, **kwargs):
    new=dict(initial)
    new.update(kwargs)
    return new

def geniss(version, home):
    """Generate the 2 inno setup files needed"""
    sysver='%d.%d' % sys.version_info[:2]
    
    template='Twisted%s-%s.win32-py%s' % ('%s', version, sysver)
    docdist=template % ''
    nodocdist=template % '_NoDocs'
    
    docdct=quickdict(pyversion=sysver, twversion=version, twhome=home,
                     pykey=r"{reg:HKLM\Software\Python\PythonCore\%s\InstallPath,|ACK}" % sysver,
                     docfile=r'Source: "%s\doc\twisteddoc.zip"; DestDir: "{app}"' % home,
                     outputbasefilename=docdist,
                     )
    nodocdct=quickdict(docdct, docfile='', outputbasefilename=nodocdist)

    print docdct
    docf=file('py%s-doc.iss' % sysver, 'w')
    docf.write(iss_template % docdct)
    docf.close()

    nodocf=file('py%s-nodoc.iss' % sysver, 'w')
    nodocf.write(iss_template % nodocdct)
    nodocf.close()

    return docdct
    
def getValueFromReg(key, value, default):
    key=winreg.Key(winreg.HKLM, key)
    try:
        return key.values[value].value
    except winreg.KeyNotFound:
        return default
    

class BuildOptions(usage.Options):
    optFlags=[["upload", "u", "Upload to sf.net using scp (requires an account with suitable permissions)"],
              ["help", 'h', "This help message"],
              ]
    optParameters=[["cyghome", "c", "",
                    "Path to the Cygwin root (as a native path, e.g. c:\cygwin)"],
                   ["twistedhome", "t", "",
                    "Path to the Twisted tree being built"],
                   ["netpbmbin", "n", "",
                    "Path to netpbm bin directory (containing pngtopnm)",],
                   ["innohome", "i", "",
                    "Path to Inno Setup's home directory (containing ISCC.exe)"],
                   ]

    def postOptions(self):
        if self['help']:
            err(str(self))
            sys.exit(2)

        successcheck=1
        if not self['cyghome']:
            self['cyghome']=getValueFromReg(r'SOFTWARE\Cygnus Solutions\Cygwin\mounts v2\/',
                                            'native', "x cygwin not found x")
        if not os.path.isdir(self['cyghome']):
            err('Cygwin must be installed!\n')
            successcheck=0

        if not self['innohome']:
            self['innohome']=getValueFromReg(r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 3_is1',
                                             "Inno Setup: App Path",
                                             "x inno not found x")
        if not os.path.isdir(self['innohome']):
            err('Inno Setup 3 must be installed!\n')
            successcheck=0

        self['pythonprefix']=sysconfig.get_config_var('prefix')

        staticpylib='%s/libs/libpython%d%d.a' % ((self['pythonprefix'],
                                                 ) + sys.version_info[:2])
        if not os.path.exists(staticpylib):
            err("%s must be present to build Twisted.\n" +
                "See http://sebsauvage.net/python/mingw.html\n" % staticpylib)
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
            netpbmbin='%s/bin' % self['cyghome']
            self['netpbmbin']=netpbmbin
        pngtopnm=os.path.join(self['netpbmbin'], 'pngtopnm.exe')
        if not os.path.isfile(pngtopnm):
            err('netpbm must be installed at %s.\n' % self['netpbmbin'])
            successcheck=0
            
        # FIXME - check if distutils has --post-install
        if not successcheck:
            err('One or more parts of your build environment are not fully set up.  Cannot continue.\n')
            sys.exit(1)

def invoke(command, args):
    """Spawn the command, and exit with an error status if it fails"""
    # replace argv[0] with just the executable because spaces muck it up
    argv=[os.path.split(command)[-1]]+args.split()
    if not os.spawnve(os.P_WAIT, command, argv, os.environ)==0:
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

    majorminor=sys.version_info[:2]

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
    def iscc(args=''):
        invoke(r'%s\ISCC.exe' % options['innohome'], args)

    # first run - no docs
    try:
        os.unlink('doc/win32doc.zip')
    except EnvironmentError:
        pass
    python('setup.py -q clean --all build --compiler=mingw32')
    geniss(version, '.')
    
    iscc('py%d.%d-nodoc.iss' % majorminor)

    # second run - docs, please
    #sh('admin/process-docs')
    #python('admin/epyrun -o doc/api')
    os.chdir('doc')
    print "Zipping..."
    infozip('-rq twisteddoc.zip examples/ -x "*CVS*" "*.cvsignore*"')
    infozip('-q twisteddoc.zip howto/*.xhtml howto/stylesheet.css howto/*.pdf')
    infozip('-q twisteddoc.zip specifications/*.xhtml')
    infozip('-q twisteddoc.zip img/*.png img/*.bmp')
    infozip('-q twisteddoc.zip vision/*.xhtml')
    infozip('-rq twisteddoc.zip api/ -x "*CVS*" "*.cvsignore" "*README"')
    os.chdir('..')

    iscc('py%d.%d-doc.iss' % majorminor)
    
    if options['upload']:
        scp('dist/%s dist/%s shell.sf.net:/home/groups/t/tw/twisted/htdocs' %
            (twisteddistnodocs, twisteddist))
        ssh('shell.sf.net chmod g+rw /home/groups/t/tw/twisted/htdocs/%s /home/groups/t/tw/twisted/htdocs/%s' %
            (twisteddistnodocs, twisteddist))
    
    raw_input('Done building Twisted! (hit enter)\n')


iss_template=r"""[Setup]
AppName=Twisted
OutputDir=dist
OutputBaseFilename=%(outputbasefilename)s
AppVerName=Twisted %(twversion)s
AppPublisher=Twisted Matrix Laboratories
AppPublisherURL=http://twistedmatrix.com/
AppSupportURL=http://twistedmatrix.com/
AppUpdatesURL=http://twistedmatrix.com/
DefaultDirName=%(pykey)s\lib\site-packages
DisableDirPage=yes
DefaultGroupName=Twisted (Python %(pyversion)s)
DisableProgramGroupPage=yes
PrivilegesRequired=admin
UninstallFilesDir=%(pykey)s

[Files]
Source: "%(twhome)s\build\lib.win32-%(pyversion)s\*.*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
%(docfile)s
Source: "%(twhome)s\build\scripts-%(pyversion)s\*.*"; DestDir: "%(pykey)s\scripts"; Flags: ignoreversion recursesubdirs
Source: "win32\twistenv.bat"; DestDir: "{app}\twisted"; Flags: ignoreversion

[UninstallDelete]
; *.pyc keeps this directory around
Type: filesandordirs; Name: "{app}\twisted"
Type: filesandordirs; Name: "{app}\TwistedDocs"

[Icons]
Name: "{group}\Manual"; Filename: "{app}\TwistedDocs\howto\index.xhtml"
Name: "{group}\API Documentation"; Filename: "{app}\TwistedDocs\api\index.html"
Name: "{group}\Twisted Command Prompt"; Filename: "{%%ComSpec}"; Parameters: "/k {app}\twisted\twistenv.bat %(pyversion)s"; WorkingDir: "{sd}\"
Name: "{group}\Application Maker"; Filename: "%(pykey)s\scripts\tktwistd.py"
Name: "{group}\TkConch (ssh)"; Filename: "%(pykey)s\scripts\tkconch.py"
Name: "{group}\Uninstall {groupname}"; Filename: "{uninstallexe}"

[Run]
Filename: "%(pykey)s\python.exe"; Parameters: "%(pykey)s\scripts\twisted_postinstall.py"
"""
    

if __name__=='__main__':
    run()
