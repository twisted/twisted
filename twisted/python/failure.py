

# System Imports
import sys
import traceback
import linecache
import string

count = 0

class Failure:
    """A basic abstraction for an error that has occurred.

    This is necessary because Python's built-in error mechanisms are
    inconvenient and not terribly self-explanitory.
    """

    pickled = 0

    def __init__(self):
        """Initialize a Failure with the current exception.
        """
        global count
        count = count + 1
        self.count = count
        self.type, self.value, tb = sys.exc_info()
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

    def printBriefTraceback(self, file=None):
        """Print a traceback as densely as possible.
        """
        if file is None: file = sys.stdout
        w = file.write
        w("Traceback! %s, %s\n" % (self.type, self.value))
        for method, filename, lineno, localVars, globalVars in self.frames:
            w('%s:%s:%s\n' % (filename, lineno, method))

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
        w('*--- End of Failure #%d ---\n' % self.count)
