#!/usr/bin/env python

#
# e.g., ./coverage.py ~/Twisted/twisted/ twisted.scripts.trial.run twisted.test.test_bounce
#

import os
import sys
import copy
import inspect

def frameFile(f):
    try:
        return os.path.abspath(inspect.getsourcefile(f.f_code))
    except:
        print 'Failed to find source for', f, f.f_code, f.f_code.co_filename
        raise

class Coverage:
    def __init__(self):
        self.files = {}
        self.__cache = {}
    
    def setHit(self, file, line):
        v = self.files.setdefault(file, {}).setdefault(line, 0)
        self.files[file][line] = v + 1
    
    def coverage(self):
        return copy.deepcopy(self.files)
    
    def summary(self, pkgRoot):
        covered = 0
        total = 0
        # Find the numbers for hit files in the given pkg
        for (F, L) in self.files.iteritems():
            if F.startswith(pkgRoot):
                total += self.linesInFile(F)
                covered += len(L)
        # Now find the files missed in the given pkg
        total += self.countMissed(pkgRoot)
        return covered, total
    
    def countMissed(self, root):
        count = 0
        for F in os.listdir(root):
            F = os.path.join(root, F)
            if os.path.isdir(F):
                count += self.countMissed(F)
            elif F not in self.files:
                count += self.linesInFile(F)
        return count
    
    def linesInFile(self, name):
        totLines = 0
        for line in file(name):
            if line.strip():
                totLines += 1
        return totLines

    def trace(self, frame, event, arg):
        try:
            r = getattr(self, 'trace_' + event)(frame, arg)
        except Exception, e:
            print e
            r = None
        return r or self.trace

    def trace_call(self, frame, arg):
        line = frame.f_lineno
        file = self.__cache.get(frame)
        if file is None:
            try:
                self.__cache[frame] = file = frameFile(frame)
            except:
                self.__cache[frame] = None
        if file is not None:
            self.setHit(file, line)

    trace_line = trace_call
    
    def trace_return(self, frame, arg):
        pass
    
    def trace_exception(self, frame, arg):
        pass

def install():
    c = Coverage()
    sys.settrace(c.trace)
    return c

def main():
    if len(sys.argv) < 3:
        fmt = 'Usage: %s <package root> <main function> [options]'
        raise SystemExit, fmt % (sys.argv[0],)
    
    c = install()
    
    root = sys.argv[1]
    chain = sys.argv[2].split('.')
    del sys.argv[1:3]
    f = reduce(getattr, chain[1:], __import__('.'.join(chain[:-1])))
    try:
        f()
    finally:
        sys.settrace(None)
        cov, tot = c.summary(root)
        print 'Lines covered: ', cov
        print 'Total lines: ', tot

if __name__ == '__main__':
    main()
