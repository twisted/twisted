import sys
import os.path
from distutils import sysconfig
import twisted.copyright
from twisted.python.runtime import platform
try:
    import win32api
    import win32con
    from win32com.shell import shell
    import pythoncom, os, sys
except ImportError:
    pass # a warning will be generated at runtime

class Shortcut: # this definitely belongs somewhere else
    """A shortcut on Win32.
    >>> sc=Shortcut(path, arguments, description, workingdir, iconpath, iconidx)
    @param path: Location of the target
    @param arguments: If path points to an executable, optional arguments to
                      pass
    @param description: Human-readable decription of target
    @param workingdir: Directory from which target is launched
    @param iconpath: Filename that contains an icon for the shortcut
    @param iconidx: If iconpath is set, optional index of the icon desired
    """
    def __init__(self, 
                 path=None,
                 arguments=None, 
                 description=None,
                 workingdir=None,
                 iconpath=None,
                 iconidx=0):
        self._base = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None,
            pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        data = map(None, 
                   [path, arguments, description, workingdir, iconpath], 
                   ("SetPath", "SetArguments", "SetDescription",
                   "SetWorkingDirectory") )
        for value, function in data:
            if value and function:
                # call function on each non-null value
                getattr(self, function)(value)
        if iconpath:
            self.SetIconLocation(iconpath, iconidx)

    def load( self, filename ):
        """Read a shortcut file from disk."""
        self._base.QueryInterface(pythoncom.IID_IPersistFile).Load(filename)
    def save( self, filename ):
        """Write the shortcut to disk.
        The file should be named something.lnk.
        """
        self._base.QueryInterface(pythoncom.IID_IPersistFile).Save(filename, 0)
    def __getattr__( self, name ):
        if name != "_base":
            return getattr(self._base, name)


def getProgramsMenuPath():
    """getProgramsMenuPath() -> String|None
    @return the filesystem location of the common Start Menu.
    """
    if not platform.isWinNT():
        return "C:\\Windows\\Start Menu\\Programs"
    keyname='SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders'
    hShellFolders=win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, 
                                        keyname, 0, win32con.KEY_READ)
    common_start_menu=win32api.RegQueryValueEx(hShellFolders, 'Common Start Menu')[0]
    return os.path.join(common_start_menu, "Programs")

def getShell32DLLPath():
    """getShell32DLLPath() -> String|None
    @return the filesystem location of shell32.dll
    """
    if platform.isWinNT():
        return os.path.join(os.getenv("SYSTEMROOT"), 
                            "system32", "shell32.dll")
    else:
        return "C:\\windows\\system\\shell32.dll"

def getBatFilename():
    """getBatFilename() -> String|None
    @return the location of the environment setup script.
    """
    python_dir=sysconfig.get_config_var("prefix")
    return os.path.join(python_dir,
                              'lib', 'site-packages', 'twisted', 'twistenv.bat')

def run():
    if sys.argv[1] == "-install": 
        whocares=install()
    elif sys.argv[1] == "-remove": 
        remove()
    else: 
        sys.stderr.write("This script is meant to be run by the Windows installer, not directly from the command line.\n")

def remove():
    pass

def install():
    """@return a list of files/directories created"""
    files_created=[]
    if platform.type != "win32":
        pass
    else:
        print "Installing environment script...",
        python_dir=sysconfig.get_config_var("prefix")
        scripts_dir=os.path.join(python_dir, "scripts")
        # FIXME - this list needs some work
        twisted_scripts=" ".join(["twistd", "mktap", "im", "generatelore",
                                    "hlint", "manhole", "t-im", "tapconvert",
                                    "html2latex", "conch",
                                    ])
        pathdict={'scripts_dir': scripts_dir,
                  'twisted_scripts': twisted_scripts}
        batch_script="""@echo off
set PATHEXT=%%PATHEXT%%;.py
set PATH=%(scripts_dir)s;%%PATH%%
set PATH
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
echo Commands available in twisted: %(twisted_scripts)s
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
""" % pathdict
        bat_location=getBatFilename()
        bat_file=open(bat_location, 'w')
        bat_file.write(batch_script)
        bat_file.close()
        file_created(bat_location)
        files_created.append(bat_location)
        print "Done."

        if not sys.modules.has_key('win32api'):
            warntext="""((( Warning )))
win32all is not available on your system, so no icons have 
been installed for Twisted.

We recommend installing win32all to get the most out of 
Twisted. This package is available at the URL: 

%(url)s

If you want icons to appear in the Start menu, you must:
1) Download & install win32all from the URL above
2) Run the Twisted installer (this program) again.
"""
            warn_dict={'url': "http://starship.python.net/crew/mhammond/win32/Downloads.html"}
            print warntext % warn_dict
        else:
            print 'Installing Icons for Twisted...',
            sys.stdout.flush()
            menu_path=os.path.join(getProgramsMenuPath(),
                                     "Twisted %s" %twisted.copyright.version)
            try:
                os.mkdir(menu_path)
                directory_created(menu_path)
                files_created.append(menu_path)
            except OSError:
                pass

            # command prompt
            shortcut=Shortcut(os.getenv("ComSpec"),
                                "/k %s" % bat_location,
                                workingdir="C:\\")
            cp_shortcut_path=os.path.join(menu_path, "Twisted Command Prompt.lnk")
            shortcut.save(cp_shortcut_path)
            file_created(cp_shortcut_path)
            files_created.append(cp_shortcut_path)

            # tkmktap
            exec_dir=sysconfig.get_config_var("exec_prefix")
            shortcut=Shortcut(os.path.join(exec_dir, "pythonw.exe"),
                              os.path.join(scripts_dir, "tkmktap.py"),
                              workingdir="C:\\")
            mktap_shortcut_path=os.path.join(menu_path, "Application Maker.lnk")
            shortcut.save(mktap_shortcut_path)
            file_created(mktap_shortcut_path)
            files_created.append(mktap_shortcut_path)
# FIXME - tktwistd doesn't actually work on Windows. No icon until fixed.
#            # tktwistd
#            shortcut=Shortcut(os.path.join(exec_dir, "pythonw.exe"),
#                              os.path.join(scripts_dir, "tktwistd.py"),
#                              workingdir="C:\\")
#            twistd_shortcut_path=os.path.join(menu_path, "Application Runner.lnk")
#            shortcut.save(twistd_shortcut_path)
#            file_created(twistd_shortcut_path)
#            files_created.append(twistd_shortcut_path)

            # uninstall
            remove_exe=os.path.join(python_dir, "RemoveTwisted.exe")
            remove_log=os.path.join(python_dir, "Twisted-wininst.log")
            icon_dll=getShell32DLLPath()
            icon_number=64 # trash can on win2k.. may be different on other OS
            remove_args='-u "%s"' % remove_log
            shortcut=Shortcut(remove_exe, 
                              remove_args, 
                              iconpath=icon_dll,
                              iconidx=icon_number)
            uninstall_shortcut_path=os.path.join(menu_path, "Uninstall Twisted.lnk")
            shortcut.save(uninstall_shortcut_path)
            file_created(uninstall_shortcut_path)
            files_created.append(uninstall_shortcut_path)
            print "Done."
        print "Post-install successful!"
    return files_created

if __name__=='__main__':
    run()
