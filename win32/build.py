import os.path, sys

from twisted.python.util import searchupwards

err=sys.stderr.write
def invoke(argv):
    """Spawn the command, and exit with an error status if it fails"""
    if not os.spawnl(os.P_WAIT, argv[0], *argv)==0:
        err("Subcommand failed: %s\n" % ' '.join(argv))
        raw_input('Press enter to quit...')
        sys.exit(1)

def run(argv=sys.argv):
    uploading=0
    if len(argv) >= 2:
        if argv[1]=='-u' or argv[1]=='--upload':
            uploading=1
    if not os.path.exists('C:/python22/libs/libpython22.a'):
        err("libpython22.a must be present to build Twisted.\n" +
            "See http://sebsauvage.net/python/mingw.html\n")
        sys.exit(1)

    # try to find twisted in the parents of the current directory first.
    # if that doesn't work, build whatever twisted is in the parents
    # of build.py itself
    home=searchupwards('.', ['setup.py'], ['twisted'])
    if not home:
        import build
        home=searchupwards(os.path.dirname(build.__file__), ['setup.py'],
                           ['twisted'])
    if home:
        os.chdir(home)
    else:
        err("Run this script from the twisted source tree.  I need to find setup.py.\n")
        sys.exit(1)

    # put home first in sys.path, we want to make sure the version
    # string matches the directory being built, not the directory
    # already installed
    sys.path.insert(0, home)
    from twisted.copyright import version

    twisteddist='Twisted-%s.win32-py2.2.exe' % version
    python='c:\\python22\\python.exe'
    scp='c:\\cygwin\\bin\\echo'
    ssh='c:\\cygwin\\bin\\ssh'
    commands=[(python, 'setup.py', 'clean', '--all'),
              (python, 'setup.py', 'build', '--compiler=mingw32'),
              (python, 'setup.py', 'bdist_wininst', 
               '--install-script=twisted_postinstall.py'),
              ]
    if uploading:
        commands.extend([(scp, 'dist/%s' % twisteddist,
                         'shell.sf.net:/home/groups/t/tw/twisted/htdocs/'),
                        (ssh, 'shell.sf.net', 'chmod', 'g+rw',
                         '/home/groups/t/tw/twisted/htdocs/%s' % twisteddist),
                        ])
    for c in commands:
        invoke(c)
    raw_input('Done!')

if __name__=='__main__':
    run()
