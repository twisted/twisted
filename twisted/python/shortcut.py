"""
A windows shortcut.

win32 only.
"""

from win32com.shell import shell
import pythoncom

class Shortcut:
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
        raise AttributeError, "%s instance has no attribute %s" % \
                (self.__class__.__name__, name)
