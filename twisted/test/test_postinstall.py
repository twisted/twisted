"""Test win32 postinstall script
"""

from twisted.trial import unittest
import sys

import os

import distutils.sysconfig
distutils.sysconfig.get_config_vars()['prefix']='.'

if os.name == 'nt':
    sys.path.insert(0, "win32")
    import twisted_postinstall
    sys.path.remove("win32")
    import os.path

    def noop1(*args, **kwargs):
        pass

    def create_shortcut(targ, title, path, args, workdir, dll=None, icon=None):
        file(path, 'w').close()
    def get_special_folder_path(*args, **kwargs):
        return ''

    for name in ['directory_created', 'file_created']:
        setattr(twisted_postinstall, name, noop1)
    twisted_postinstall.create_shortcut=create_shortcut
    twisted_postinstall.get_special_folder_path=get_special_folder_path

    class PostinstallTest(unittest.TestCase):
        def testInstall(self):
            stdout_save=sys.stdout
            output=open("install.stdout.txt", 'w')
            sys.stdout=output
            files=twisted_postinstall.install()
            sys.stdout=stdout_save
            output.close()
            for f in files:
                assert os.path.exists(f)

        def testRemove(self):
            assert twisted_postinstall.remove() is None
