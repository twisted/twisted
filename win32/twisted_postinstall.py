#!/usr/bin/env python

# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# post-install

import sys
import os.path
from distutils import sysconfig
import twisted.copyright
from twisted.python import runtime

if 'file_created' not in dir(__builtins__):
    def noop(*args, **kwargs):
        pass
    file_created=directory_created=noop


def getProgramsMenuPath():
    """getProgramsMenuPath() -> String|None
    @return the filesystem location of the common Start Menu.
    """

    try:
        return get_special_folder_path("CSIDL_COMMON_PROGRAMS")
    except OSError: # probably Win98
        return get_special_folder_path("CSIDL_PROGRAMS")

def getShell32DLLPath():
    """getShell32DLLPath() -> String|None
    @return the filesystem location of shell32.dll
    """
    # If SYSTEMROOT is not found (on Win98), guess the name
    # of the windows directory
    try:
        get_special_folder_path("CSIDL_COMMON_PROGRAMS")
        return os.path.join(os.getenv("SYSTEMROOT"),
                            "system32", "shell32.dll"), 64
    except OSError: # probably Win98
        return os.path.join(os.getenv("windir"),
                            "system", "shell32.dll"), 32

def getBatFilename():
    """getBatFilename() -> String|None
    @return the location of the environment setup script.
    """
    python_dir=sysconfig.get_config_var("prefix")
    return os.path.join(python_dir,
                              'lib', 'site-packages', 'twisted', 'twistenv.bat')

def run(argv=sys.argv):
    if argv[1] == "-install": 
        whocares=install()
    elif argv[1] == "-remove": 
        remove()
    else: 
        sys.stderr.write("This script is meant to be run by the Windows installer, not directly from the command line.\n")

def remove():
    pass

def install():
    """@return a list of files/directories created"""
    files_created=[]
    if sys.platform != "win32":
        pass
    else:
        print "Installing environment script...",
        python_dir=sysconfig.get_config_var("prefix")
        scripts_dir=os.path.join(python_dir, "scripts")
        # FIXME - this list needs some work
        advertised_scripts=" ".join(["twistd", "mktap", "manhole",
                                     "tapconvert", "ckeygen", "trial",
                                     "coil", "lore", "websetroot", 
                                     ])
        # The following scripts are not advertised for the following reasons
        #  conch - issues an exception when run with no arguments
        #  im, t-im - issue exceptions for missing gtk when run
        #  tap2deb - platform-specific
        #  tk* - no need; the ones that work have icons in the start menu
        pathdict={'scripts_dir': scripts_dir,
                  'advertised_scripts': advertised_scripts}
        batch_script="""@echo off
set PATHEXT=%%PATHEXT%%;.py
set PATH=%(scripts_dir)s;%%PATH%%
set PATH
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
echo Commands available in twisted: %(advertised_scripts)s
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
""" % pathdict
        bat_location=getBatFilename()
        bat_dir=os.path.dirname(bat_location)
        try:
            os.makedirs(bat_dir)
        except OSError:
            pass
        bat_file=open(bat_location, 'w')
        bat_file.write(batch_script)
        bat_file.close()
        file_created(bat_location)
        files_created.append(bat_location)
        print "Done."

        print 'Installing Icons for Twisted...',
        sys.stdout.flush()
        menu_path=os.path.join(getProgramsMenuPath(),
                               "Twisted (Python %s)" % sys.version[:3])
        try:
            os.mkdir(menu_path)
            directory_created(menu_path)
            files_created.append(menu_path)
        except OSError:
            pass

        # command prompt
        cp_shortcut_path=os.path.join(menu_path, "Twisted Command Prompt.lnk")
        create_shortcut(os.getenv("ComSpec"),
                        "Twisted Command Prompt",
                        cp_shortcut_path,
                        "/k %s" % bat_location,
                        "C:\\")
        file_created(cp_shortcut_path)
        files_created.append(cp_shortcut_path)
        if not runtime.platform.isWinNT():
            win98_pathname = os.path.splitext(cp_shortcut_path)[0] + ".pif"
            file_created(win98_pathname)
            files_created.append(win98_pathname)

        # tkmktap
        exec_dir=sysconfig.get_config_var("exec_prefix")
        mktap_shortcut_path=os.path.join(menu_path, "Application Maker.lnk")
        create_shortcut(os.path.join(exec_dir, "pythonw.exe"),
                        "Application Maker",
                        mktap_shortcut_path,
                        os.path.join(scripts_dir, "tkmktap.py"),
                        "C:\\")
        file_created(mktap_shortcut_path)
        files_created.append(mktap_shortcut_path)

# FIXME - tktwistd doesn't actually work on Windows. No icon until fixed.
#        # tktwistd
#        shortcut=Shortcut(os.path.join(exec_dir, "pythonw.exe"),
#                          os.path.join(scripts_dir, "tktwistd.py"),
#                          workingdir="C:\\")
#        twistd_shortcut_path=os.path.join(menu_path, "Application Runner.lnk")
#        shortcut.save(twistd_shortcut_path)
#        file_created(twistd_shortcut_path)
#        files_created.append(twistd_shortcut_path)

        # tkconch
        # XXX: Works only of Crypto is available...
        conch_shortcut_path=os.path.join(menu_path, "TkConch (ssh).lnk")
        create_shortcut(os.path.join(exec_dir, "pythonw.exe"),
                        "TkConch",
                        conch_shortcut_path,
                        os.path.join(scripts_dir, "tkconch.py"),
                        "C:\\")
        file_created(conch_shortcut_path)
        files_created.append(conch_shortcut_path)

        # uninstall
        remove_exe=os.path.join(python_dir, "RemoveTwisted.exe")
        remove_log=os.path.join(python_dir, "Twisted-wininst.log")
        icon_dll, icon_number=getShell32DLLPath()
        remove_args='-u "%s"' % remove_log
        uninstall_shortcut_path=os.path.join(menu_path, "Uninstall Twisted.lnk")

        create_shortcut(remove_exe,
                        "Remove",
                        uninstall_shortcut_path,
                        remove_args,
                        "",
                        icon_dll,
                        icon_number)
        file_created(uninstall_shortcut_path)
        files_created.append(uninstall_shortcut_path)
        print "Done."
        print "Post-install successful!"
    return files_created

if __name__=='__main__':
    run()
