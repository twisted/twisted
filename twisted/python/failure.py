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


# System Imports
import sys
import traceback
import linecache
import string
from cStringIO import StringIO

count = 0

class Failure:
    """A basic abstraction for an error that has occurred.

    This is necessary because Python's built-in error mechanisms are
    inconvenient for asynchronous communication.
    """

    pickled = 0

    def __init__(self, exc_value=None, exc_type=None, exc_tb=None):
        """Initialize me with an explanation of the error.

        By default, this will use the current exception (sys.exc_info()).
        However, if you want to specify a particular kind of failure, you can
        pass an exception as an argument.
        """
        global count
        count = count + 1
        self.count = count
        self.type, self.value, tb = None, None, None
        if exc_value is None:
            self.type, self.value, tb = sys.exc_info()
        elif exc_type is None:
            self.type = exc_value.__class__
            self.value = exc_value
        else:
            self.type = exc_type
            self.value = exc_value
        frames = self.frames = []
        while tb is not None:
            f = tb.tb_frame
            localz = f.f_locals.copy()
            if f.f_locals is f.f_globals:
                globalz = {}
            else:
                globalz = f.f_globals.copy()
            frames.append([
                f.f_code.co_name,
                f.f_code.co_filename,
                tb.tb_lineno,
                localz.items(),
                globalz.items(),
                ])
            tb = tb.tb_next

    def getErrorMessage(self):
        if isinstance(self.value, Failure):
            return self.value.getErrorMessage()
        return str(self.value)

    def trap(self, *errorTypes):
        """Trap this failure if its type is in a predetermined list.

        This allows you to trap a Failure in an error callback.  It will be
        automatically re-raised if it is not a type that you expect.
        """
        for errorType in errorTypes:
            if (self.type == errorType or
                issubclass(self.type, errorType)):
                break
        else:
            raise self

    def getBriefTraceback(self):
        io = StringIO()
        self.printBriefTraceback(file=io)
        return io.getvalue()

    def __repr__(self):
        return "[Failure instance: %s]" % self.getBriefTraceback()

    def __getstate__(self):
        """Avoid pickling objects in the traceback.
        """
        c = self.__dict__.copy()
        frames = c['frames'] = []
        stringize = lambda (x, y): (x, repr(y))
        for m, f, l, lo, gl in self.frames:
            frames.append([m, f, l, map(stringize, lo), map(stringize, gl)])
        c['pickled'] = 1
        return c

    def printTraceback(self, file=None):
        """Emulate Python's standard error reporting mechanism.
        """
        if file is None: file = sys.stdout
        w = file.write
        w( 'Traceback (most recent call last):\n')
        for method, filename, lineno, localVars, globalVars in self.frames:
            w( '  File "%s", line %s, in %s\n' % (filename, lineno, method))
            w( '    %s\n' % string.strip(linecache.getline(filename, lineno)))
            # w( '\n')
        w("%s: %s\n" % (str(self.type), str(self.value)))
        if isinstance(self.value, Failure):
            file.write(" (chained Failure)\n")
            self.value.printTraceback(file)

    def printBriefTraceback(self, file=None):
        """Print a traceback as densely as possible.
        """
        if file is None: file = sys.stdout
        w = file.write
        w("Traceback! %s, %s\n" % (self.type, self.value))
        for method, filename, lineno, localVars, globalVars in self.frames:
            w('%s:%s:%s\n' % (filename, lineno, method))
        if isinstance(self.value, Failure):
            file.write(" (chained Failure)\n")
            self.value.printBriefTraceback(file)

    def printDetailedTraceback(self, file=None):
        """Print a traceback with detailed locals and globals information.
        """
        if file is None: file = sys.stdout
        w = file.write
        w( '*--- Failure #%d%s---\n' %
           (self.count,
            (self.pickled and ' (pickled) ') or ' '))
        for method, filename, lineno, localVars, globalVars in self.frames:
            w("%s:%d: %s(...)\n" % (filename, lineno, method))
            w(' [ Locals ]\n')
            for name, val in localVars:
                w("  %s : %s\n" %  (name,(self.pickled and val) or repr(val)))
            w(' ( Globals )\n')
            for name, val in globalVars:
                w("  %s : %s\n" %  (name,(self.pickled and val) or repr(val)))
        if isinstance(self.value, Failure):
            w(" (chained Failure)\n")
            self.value.printDetailedTraceback(file)
        w('*--- End of Failure #%d ---\n' % self.count)
