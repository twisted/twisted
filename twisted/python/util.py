# -*- test-case-name: twisted.test.test_util -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from __future__ import nested_scopes, generators

__version__ = '$Revision: 1.51 $'[11:-2]

import os, sys, hmac, errno, new, inspect

from UserDict import UserDict

class InsensitiveDict:
    """Dictionary, that has case-insensitive keys.

    Normally keys are retained in their original form when queried with
    .keys() or .items().  If initialized with preserveCase=0, keys are both
    looked up in lowercase and returned in lowercase by .keys() and .items().
    """
    """
    Modified recipe at
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66315 originally
    contributed by Sami Hangaslammi.
    """

    def __init__(self, dict=None, preserve=1):
        """Create an empty dictionary, or update from 'dict'."""
        self.data = {}
        self.preserve=preserve
        if dict:
            self.update(dict)

    def __delitem__(self, key):
        k=self._lowerOrReturn(key)
        del self.data[k]

    def _lowerOrReturn(self, key):
        if isinstance(key, str) or isinstance(key, unicode):
            return key.lower()
        else:
            return key

    def __getitem__(self, key):
        """Retrieve the value associated with 'key' (in any case)."""
        k = self._lowerOrReturn(key)
        return self.data[k][1]

    def __setitem__(self, key, value):
        """Associate 'value' with 'key'. If 'key' already exists, but
        in different case, it will be replaced."""
        k = self._lowerOrReturn(key)
        self.data[k] = (key, value)

    def has_key(self, key):
        """Case insensitive test whether 'key' exists."""
        k = self._lowerOrReturn(key)
        return self.data.has_key(k)
    __contains__=has_key

    def _doPreserve(self, key):
        if not self.preserve and (isinstance(key, str)
                                  or isinstance(key, unicode)):
            return key.lower()
        else:
            return key

    def keys(self):
        """List of keys in their original case."""
        return list(self.iterkeys())

    def values(self):
        """List of values."""
        return list(self.itervalues())

    def items(self):
        """List of (key,value) pairs."""
        return list(self.iteritems())

    def get(self, key, default=None):
        """Retrieve value associated with 'key' or return default value
        if 'key' doesn't exist."""
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default):
        """If 'key' doesn't exists, associate it with the 'default' value.
        Return value associated with 'key'."""
        if not self.has_key(key):
            self[key] = default
        return self[key]

    def update(self, dict):
        """Copy (key,value) pairs from 'dict'."""
        for k,v in dict.items():
            self[k] = v

    def __repr__(self):
        """String representation of the dictionary."""
        items = ", ".join([("%r: %r" % (k,v)) for k,v in self.items()])
        return "InsensitiveDict({%s})" % items

    def iterkeys(self):
        for v in self.data.itervalues():
            yield self._doPreserve(v[0])

    def itervalues(self):
        for v in self.data.itervalues():
            yield v[1]

    def iteritems(self):
        for (k, v) in self.data.itervalues():
            yield self._doPreserve(k), v

    def popitem(self):
        i=self.items()[0]
        del self[i[0]]
        return i

    def clear(self):
        for k in self.keys():
            del self[k]

    def copy(self):
        return InsensitiveDict(self, self.preserve)

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        for k,v in self.items():
            if not (k in other) or not (other[k]==v):
                return 0
        return len(self)==len(other)

class OrderedDict(UserDict):
    """A UserDict that preserves insert order whenever possible."""
    def __init__(self, dict=None, **kwargs):
        self._order = []
        self.data = {}
        if dict is not None:
            if hasattr(dict,'keys'):
                self.update(dict)
            else:
                for k,v in dict: # sequence
                    self[k] = v
        if len(kwargs):
            self.update(kwargs)
    def __repr__(self):
        return '{'+', '.join([('%r: %r' % item) for item in self.items()])+'}'

    def __setitem__(self, key, value):
        if not self.has_key(key):
            self._order.append(key)
        UserDict.__setitem__(self, key, value)

    def copy(self):
        return self.__class__(self)

    def __delitem__(self, key):
        UserDict.__delitem__(self, key)
        self._order.remove(key)

    def iteritems(self):
        for item in self._order:
            yield (item, self[item])

    def items(self):
        return list(self.iteritems())

    def itervalues(self):
        for item in self._order:
            yield self[item]

    def values(self):
        return list(self.itervalues())

    def iterkeys(self):
        return iter(self._order)

    def keys(self):
        return list(self._order)

    def popitem(self):
        key = self._order[-1]
        value = self[key]
        del self[key]
        return (key, value)

    def setdefault(self, item, default):
        if self.has_key(item):
            return self[item]
        self[item] = default
        return default

    def update(self, d):
        for k, v in d.items():
            self[k] = v

def uniquify(lst):
    """Make the elements of a list unique by inserting them into a dictionary.
    This must not change the order of the input lst.
    """
    dct = {}
    result = []
    for k in lst:
        if not dct.has_key(k): result.append(k)
        dct[k] = 1
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
    allPlugins = filter(os.path.isdir, [systemPlugins, userPlugins, confPlugins])
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


def _getpass(prompt):
    """Helper to turn IOErrors into KeyboardInterrupts"""
    import getpass
    try:
        return getpass.getpass(prompt)
    except IOError, e:
        if e.errno == errno.EINTR:
            raise KeyboardInterrupt
        raise
    except EOFError:
        raise KeyboardInterrupt

def getPassword(prompt = 'Password: ', confirm = 0, forceTTY = 0,
                confirmPrompt = 'Confirm password: ',
                mismatchMessage = "Passwords don't match."):
    """Obtain a password by prompting or from stdin.

    If stdin is a terminal, prompt for a new password, and confirm (if
    C{confirm} is true) by asking again to make sure the user typed the same
    thing, as keystrokes will not be echoed.

    If stdin is not a terminal, and C{forceTTY} is not true, read in a line
    and use it as the password, less the trailing newline, if any.  If
    C{forceTTY} is true, attempt to open a tty and prompt for the password
    using it.  Raise a RuntimeError if this is not possible.

    @returns: C{str}
    """
    isaTTY = hasattr(sys.stdin, 'isatty') and sys.stdin.isatty()

    old = None
    try:
        if not isaTTY:
            if forceTTY:
                try:
                    old = sys.stdin, sys.stdout
                    sys.stdin = sys.stdout = open('/dev/tty', 'r+')
                except:
                    raise RuntimeError("Cannot obtain a TTY")
            else:
                password = sys.stdin.readline()
                if password[-1] == '\n':
                    password = password[:-1]
                return password

        while 1:
            try1 = _getpass(prompt)
            if not confirm:
                return try1
            try2 = _getpass(confirmPrompt)
            if try1 == try2:
                return try1
            else:
                sys.stderr.write(mismatchMessage + "\n")
    finally:
        if old:
            sys.stdin.close()
            sys.stdin, sys.stdout = old


def dict(*a, **k):
    import warnings
    import __builtin__
    warnings.warn('twisted.python.util.dict is deprecated.  Use __builtin__.dict instead')
    return __builtin__.dict(*a, **k)

def println(*a):
    sys.stdout.write(' '.join(map(str, a))+'\n')

# XXX
# This does not belong here
# But where does it belong?

def str_xor(s, b):
    return ''.join([chr(ord(c) ^ b) for c in s])

def keyed_md5(secret, challenge):
    """Create the keyed MD5 string for the given secret and challenge."""
    import warnings
    warnings.warn(
        "keyed_md5() is deprecated.  Use the stdlib module hmac instead.",
        DeprecationWarning, stacklevel=2
    )
    return hmac.HMAC(secret, challenge).hexdigest()

def makeStatBar(width, maxPosition, doneChar = '=', undoneChar = '-', currentChar = '>'):
    """Creates a function that will return a string representing a progress bar.
    """
    aValue = width / float(maxPosition)
    def statBar(position, force = 0, last = ['']):
        assert len(last) == 1, "Don't mess with the last parameter."
        done = int(aValue * position)
        toDo = width - done - 2
        result = "[%s%s%s]" % (doneChar * done, currentChar, undoneChar * toDo)
        if force:
            last[0] = result
            return result
        if result == last[0]:
            return ''
        last[0] = result
        return result

    statBar.__doc__ = """statBar(position, force = 0) -> '[%s%s%s]'-style progress bar

    returned string is %d characters long, and the range goes from 0..%d.
    The 'position' argument is where the '%s' will be drawn.  If force is false,
    '' will be returned instead if the resulting progress bar is identical to the
    previously returned progress bar.
""" % (doneChar * 3, currentChar, undoneChar * 3, width, maxPosition, currentChar)
    return statBar

def spewer(frame, s, ignored):
    """A trace function for sys.settrace that prints every function or method call."""
    from twisted.python import reflect
    if frame.f_locals.has_key('self'):
        se = frame.f_locals['self']
        if hasattr(se, '__class__'):
            k = reflect.qual(se.__class__)
        else:
            k = reflect.qual(type(se))
        print 'method %s of %s at %s' % (
            frame.f_code.co_name, k, id(se)
        )
    else:
        print 'function %s in %s, line %s' % (
            frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_lineno)

def searchupwards(start, files=[], dirs=[]):
    """Walk upwards from start, looking for a directory containing
    all files and directories given as arguments::
    >>> searchupwards('.', ['foo.txt'], ['bar', 'bam'])

    If not found, return None
    """
    start=os.path.abspath(start)
    parents=start.split(os.sep)
    exists=os.path.exists; join=os.sep.join; isdir=os.path.isdir
    while len(parents):
        candidate=join(parents)+os.sep
        allpresent=1
        for f in files:
            if not exists("%s%s" % (candidate, f)):
                allpresent=0
                break
        if allpresent:
            for d in dirs:
                if not isdir("%s%s" % (candidate, d)):
                    allpresent=0
                    break
        if allpresent: return candidate
        parents.pop(-1)
    return None


class LineLog:
    """
    A limited-size line-based log, useful for logging line-based
    protocols such as SMTP.

    When the log fills up, old entries drop off the end.
    """
    def __init__(self, size=10):
        """
        Create a new log, with size lines of storage (default 10).
        A log size of 0 (or less) means an infinite log.
        """
        if size < 0:
            size = 0
        self.log = [None]*size
        self.size = size

    def append(self,line):
        if self.size:
            self.log[:-1] = self.log[1:]
            self.log[-1] = line
        else:
            self.log.append(line)

    def str(self):
        return '\n'.join(filter(None,self.log))

    def __getitem__(self, item):
        return filter(None,self.log)[item]

    def clear(self):
        """Empty the log"""
        self.log = [None]*self.size

def raises(exception, f, *args, **kwargs):
    """Determine whether the given call raises the given exception"""
    try:
        f(*args, **kwargs)
    except exception:
        return 1
    return 0

class IntervalDifferential:
    """
    Given a list of intervals, generate the amount of time to sleep between
    \"instants\".

    For example, given 7, 11 and 13, the three (infinite) sequences::

        7 14 21 28 35 ...
        11 22 33 44 ...
        13 26 39 52 ...

    will be generated, merged, and used to produce::

        (7, 0) (4, 1) (2, 2) (1, 0) (7, 0) (1, 1) (4, 2) (2, 0) (5, 1) (2, 0)

    New intervals may be added or removed as iteration proceeds using the
    proper methods.
    """

    def __init__(self, intervals, default=60):
        """
        @type intervals: C{list} of C{int}, C{long}, or C{float} param
        @param intervals: The intervals between instants.

        @type default: C{int}, C{long}, or C{float}
        @param default: The duration to generate if the intervals list
        becomes empty.
        """
        self.intervals = intervals[:]
        self.default = default

    def __iter__(self):
        return _IntervalDifferentialIterator(self.intervals, self.default)

class _IntervalDifferentialIterator:
    def __init__(self, i, d):

        self.intervals = [[e, e, n] for (e, n) in zip(i, range(len(i)))]
        self.default = d
        self.last = 0

    def next(self):
        if not self.intervals:
            return (self.default, None)
        last, index = self.intervals[0][0], self.intervals[0][2]
        self.intervals[0][0] += self.intervals[0][1]
        self.intervals.sort()
        result = last - self.last
        self.last = last
        return result, index

    def addInterval(self, i):
        if self.intervals:
            delay = self.intervals[0][0] - self.intervals[0][1]
            self.intervals.append([delay + i, i, len(self.intervals)])
            self.intervals.sort()
        else:
            self.intervals.append([i, i, 0])

    def removeInterval(self, interval):
        for i in range(len(self.intervals)):
            if self.intervals[i][1] == interval:
                index = self.intervals[i][2]
                del self.intervals[i]
                for i in self.intervals:
                    if i[2] > index:
                        i[2] -= 1
                return
        raise ValueError, "Specified interval not in IntervalDifferential"


class FancyStrMixin:
    """
    Set showAttributes to a sequence of strings naming attributes, OR
    sequences of (attributeName, displayName, formatCharacter)
    """
    showAttributes = ()
    def __str__(self):
        r = ['<', hasattr(self, 'fancybasename') and self.fancybasename or self.__class__.__name__]
        for attr in self.showAttributes:
            if isinstance(attr, str):
                r.append(' %s=%r' % (attr, getattr(self, attr)))
            else:
                r.append((' %s=' + attr[2]) % (attr[1], getattr(self, attr[0])))
        r.append('>')
        return ''.join(r)
    __repr__ = __str__

class FancyEqMixin:
    compareAttributes = ()
    def __eq__(self, other):
        if not self.compareAttributes:
            return self is other
        #XXX Maybe get rid of this, and rather use hasattr()s
        if not isinstance(other, self.__class__):
            return False
        for attr in self.compareAttributes:
            if not getattr(self, attr) == getattr(other, attr):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

def dsu(list, key):
    L2 = [(key(e), i, e) for (i, e) in zip(range(len(list)), list)]
    L2.sort()
    return [e[2] for e in L2]

try:
    import pwd, grp
    from os import setgroups, getgroups
    
    def _setgroups_until_success(l):
        while(1):
            # NASTY NASTY HACK (but glibc does it so it must be okay):
            # In case sysconfig didn't give the right answer, find the limit
            # on max groups by just looping, trying to set fewer and fewer
            # groups each time until it succeeds.
            try:
                setgroups(l)
            except ValueError:
                # This exception comes from python itself restricting
                # number of groups allowed.
                if len(l) > 1:
                    del l[-1]
                else:
                    raise
            except OSError, e:
                if e.errno == errno.EINVAL and len(l) > 1:
                    # This comes from the OS saying too many groups
                    del l[-1]
                else:
                    raise
            else:
                # Success, yay!
                return
            
    def initgroups(uid, primaryGid):
        """Initializes the group access list.

        This is done by reading the group database /etc/group and using all
        groups of which C{uid} is a member.  The additional group
        C{primaryGid} is also added to the list.

        If the given user is a member of more than C{NGROUPS}, arbitrary
        groups will be silently discarded to bring the number below that
        limit.
        """       
        try:
            # Try to get the maximum number of groups
            max_groups = os.sysconf("SC_NGROUPS_MAX")
        except:
            # No predefined limit
            max_groups = 0
        
        username = pwd.getpwuid(uid)[0]
        l = []
        if primaryGid is not None:
            l.append(primaryGid)
        for groupname, password, gid, userlist in grp.getgrall():
            if username in userlist:
                l.append(gid)
                if len(l) == max_groups:
                    break # No more groups, ignore any more
        try:
            _setgroups_until_success(l)
        except OSError, e:
            # We might be able to remove this code now that we
            # don't try to setgid/setuid even when not asked to.
            if e.errno == errno.EPERM:
                for g in getgroups():
                    if g not in l:
                        raise
            else:
                raise
                                    

except:
    def initgroups(uid, primaryGid):
        """Do nothing.

        Underlying platform support require to manipulate groups is missing.
        """


def switchUID(uid, gid, euid=False):
    if euid:
        setuid = os.seteuid
        setgid = os.setegid
    else:
        setuid = os.setuid
        setgid = os.setgid
    if gid is not None:
        setgid(gid)
    if uid is not None:
        initgroups(uid, gid)
        setuid(uid)


class SubclassableCStringIO(object):
    """A wrapper around cStringIO to allow for subclassing"""
    __csio = None

    def __init__(self, *a, **kw):
        from cStringIO import StringIO
        self.__csio = StringIO(*a, **kw)

    def __iter__(self):
        return self.__csio.__iter__()

    def next(self):
        return self.__csio.next()

    def close(self):
        return self.__csio.close()

    def isatty(self):
        return self.__csio.isatty()

    def seek(self, pos, mode=0):
        return self.__csio.seek(pos, mode)

    def tell(self):
        return self.__csio.tell()

    def read(self, n=-1):
        return self.__csio.read(n)

    def readline(self, length=None):
        return self.__csio.readline(length)

    def readlines(self, sizehint=0):
        return self.__csio.readlines(sizehint)

    def truncate(self, size=None):
        return self.__csio.truncate(size)

    def write(self, s):
        return self.__csio.write(s)

    def writelines(self, list):
        return self.__csio.writelines(list)

    def flush(self):
        return self.__csio.flush()

    def getvalue(self):
        return self.__csio.getvalue()

def moduleMovedForSplit(origModuleName, newModuleName, moduleDesc,
                        projectName, projectURL, globDict):
    from twisted.python import reflect
    modoc = """
%(moduleDesc)s

This module is DEPRECATED. It has been split off into a third party
package, Twisted %(projectName)s. Please see %(projectURL)s.

This is just a place-holder that imports from the third-party %(projectName)s
package for backwards compatibility. To use it, you need to install
that package.
""" % {'moduleDesc': moduleDesc,
       'projectName': projectName,
       'projectURL': projectURL}

    #origModule = reflect.namedModule(origModuleName)
    try:
        newModule = reflect.namedModule(newModuleName)
    except ImportError:
        raise ImportError("You need to have the Twisted %s "
                          "package installed to use %s. "
                          "See %s."
                          % (projectName, origModuleName, projectURL))

    # Populate the old module with the new module's contents
    for k,v in vars(newModule).items():
        globDict[k] = v
    globDict['__doc__'] = modoc
    import warnings
    warnings.warn("%s has moved to %s. See %s." % (origModuleName, newModuleName,
                                                   projectURL),
                  DeprecationWarning, stacklevel=3)
    return


def untilConcludes(f, *a, **kw):
    while True:
        try:
            return f(*a, **kw)
        except (IOError, OSError), e:
            if e.args[0] == errno.EINTR:
                continue
            raise

# A value about twice as large as any Python int, to which negative values
# from id() will be added, moving them into a range which should begin just
# above where positive values from id() leave off.
_HUGEINT = (sys.maxint + 1L) * 2L
def unsignedID(obj):
    """
    Return the id of an object as an unsigned number so that its hex
    representation makes sense
    """
    rval = id(obj)
    if rval < 0:
        rval += _HUGEINT
    return rval

def mergeFunctionMetadata(f, g):
    """
    Overwrite C{g}'s docstring and name with values from C{f}.  Update
    C{g}'s instance dictionary with C{f}'s.
    """
    try:
        g.__doc__ = f.__doc__
    except (TypeError, AttributeError):
        pass
    try:
        g.__dict__.update(f.__dict__)
    except (TypeError, AttributeError):
        pass
    try:
        g.__name__ = f.__name__
    except TypeError:
        try:
            g = new.function(
                g.func_code, g.func_globals,
                f.__name__, inspect.getargspec(g)[-1],
                g.func_closure)
        except TypeError:
            pass
    return g

__all__ = [
    "uniquify", "padTo", "getPluginDirs", "addPluginDir", "sibpath",
    "getPassword", "dict", "println", "keyed_md5", "makeStatBar",
    "OrderedDict", "InsensitiveDict", "spewer", "searchupwards", "LineLog",
    "raises", "IntervalDifferential", "FancyStrMixin", "FancyEqMixin",
    "dsu", "switchUID", "SubclassableCStringIO", "moduleMovedForSplit",
    "unsignedID", "mergeFunctionMetadata",
]
