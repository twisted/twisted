
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

import os, sys

def uniquify(lst):
    """Make the elements of a list unique by inserting them into a dictionary.
    """
    dict = {}
    result = []
    for k in lst:
        if not dict.has_key(k): result.append(k)
        dict[k] = 1
    return result

def padTo(n, seq, default=None):
    """Pads a sequence out to n elements,

    filling in with a default value if it is not long enough.

    If the input sequence is longer than n, raises ValueError.

    Details, details:
    This returns a new list; it does not extend the original sequence.
    The new list contains the values of the original sequence, not copies.
    """

    if len(seq) > n:
        raise ValueError, "%d elements is more than %d." % (len(seq), n)

    blank = [default] * n

    blank[:len(seq)] = list(seq)

    return blank

def getPluginDirs():
    import twisted
    systemPlugins = os.path.join(os.path.dirname(os.path.dirname(
                            os.path.abspath(twisted.__file__))), 'plugins')
    userPlugins = os.path.expanduser("~/TwistedPlugins")
    confPlugins = os.path.expanduser("~/.twisted")
    allPlugins = [systemPlugins, userPlugins, confPlugins]
    return allPlugins

def addPluginDir():
    sys.path.extend(getPluginDirs())

def sibpath(path, sibling):
    """Return the path to a sibling of a file in the filesystem.

    This is useful in conjunction with the special __file__ attribute
    that Python provides for modules, so modules can load associated
    resource files.
    """
    return os.path.join(os.path.dirname(os.path.abspath(path)), sibling)


def getPassword(prompt = '', confirm = 0):
    """Obtain a password by prompting or from stdin.

    If stdin is a terminal, prompt for a new password, and confirm (if
    C{confirm} is true) by asking again to make sure the user typed the same
    thing, as keystrokes will not be echoed.

    If stdin is not a terminal, read in a line and use it as the password,
    less the trailing newline, if any.

    @returns: C{str}
    """
    # If standard input is a terminal, I prompt for a password and
    # confirm it.  Otherwise, I use the first line from standard
    # input, stripping off a trailing newline if there is one.
    if os.isatty(sys.stdin.fileno()):
        gotit = 0
        while not gotit:
            try1 = getpass.getpass(prompt)
            if not confirm:
                return try1
            try2 = getpass.getpass("Confirm: ")
            if try1 == try2:
                gotit = 1
            else:
                sys.stderr.write("Passwords don't match.\n")
        else:
            password = try1
    else:
        password = sys.stdin.readline()
        if password[-1] == '\n':
            password = password[:-1]
    return password


def dict(*a, **k):
    import warnings
    import twisted.python.compat
    warnings.warn('twisted.python.util.dict is deprecated.  Use twisted.python.compat.dict instead')
    return twisted.python.compat.dict(*a, **k)
