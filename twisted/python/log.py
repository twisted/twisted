"""
twisted.log: Logfile and multi-threaded file support.
"""


import sys
import string
import cStringIO
import time

StringIO = cStringIO
del cStringIO

def _no_log_output(func, *args, **kw):
    io = StringIO.StringIO()
    old = sys.stdout
    sys.stdout = io
    try:
        result = apply(func, args, kw)
        return result, io.getvalue()
    finally:
        sys.stdout = old
        

def _log_output(func, *args, **kw):
    io = Output()
    sys.stdout.ownable.own(io)
    try:
        result = apply(func, args, kw)
        return result, io.getvalue()
    finally:
        sys.stdout.ownable.disown(io)
        

def output(func, *args, **kw):
    return apply([_no_log_output, _log_output]
                 [hasattr(sys.stdout, 'ownable')],
                 (func,)+args,kw)
        
        
file_protocol = ['close', 'closed', 'fileno',
                 'flush', 'isatty', 'mode',
                 'name', 'read', 'readinto',
                 'readline', 'readlines', 'seek',
                 'softspace', 'tell', 'truncate',
                 'write', 'writelines']

# Prevent logfile from being erased on reload.  This only works in cpython.
try:
    logfile
except NameError:
    logfile = sys.stdout

def write(stuff):
    logfile.write(str(stuff))
    logfile.flush()

def msg(stuff):
    logfile.write(str(stuff)+"\n")
    logfile.flush()


def startLogging(file):
    global logfile
    import threadable
    import sys
    logfile = Log(file, threadable.dispatcher)
    lgr = Logger()
    threadable.dispatcher.defaultOwner = lgr
    sys.stdout = sys.stderr = logfile
    msg( "Log opened." )

class Logger:
    """
    This represents a class which may 'own' a log.
    """
    written = 1
    def log(self,bytes):
        if not bytes: return
        written = self.written
        if bytes[-1]=='\n':
            self.written = self.written+1
            bytes = string.replace(bytes[:-1],'\n','\n'+self.__prefix())+'\n'
        else:
            bytes = string.replace(bytes,'\n','\n'+self.__prefix())
        if written:
            bytes = self.__prefix()+bytes
            self.written = self.written-1
        # TODO: make this cache everything after the last newline so
        # that multiple threads using "print x, y" style logging get x
        # and y on the same line.
        return bytes

    def __prefix(self):
        y,mon,d,h,min, i,g,no,re = time.localtime(time.time())
        return ("%0.2d/%0.2d/%0.4d %0.2d:%0.2d [%s] " %
                 (d,mon,y,h,min , self.logPrefix()))

    def logPrefix(self):
        """
        Override this method to insert custom logging behavior.  Its
        return value will be inserted in front of every line.  It may
        be called more times than the number of output lines.
        """
        return '-'


class Output:
    """
    This represents a class which traps output.
    """
    def __init__(self):
        self.io = StringIO.StringIO()

        
    def log(self, bytes):
        self.io.write(bytes)
        
        
    def getvalue(self):
        return self.io.getvalue()
        
    
class Log:
    __synchronized__ = ['write',
                        'writelines']
    
    def __init__(self, file, ownable):

        """
        Log(file, ownable)
        
        This will create a Log file (intended to be written to with
        'print', but usable from anywhere that a file is) from a file
        and an 'ownable' object.  The ownable object must have a
        method called 'owner', which takes no arguments and returns a
        Logger.
        """
        
        self.file = file
        for attr in file_protocol:
            if not hasattr(self,attr):
                setattr(self,attr,getattr(file,attr))
        self.ownable = ownable
        
    def write(self,bytes):
        if not bytes:
            return
        logger = self.ownable.owner()
        if logger:
            bytes = logger.log(bytes)
        if not bytes:
            return
        self.file.write(bytes)
        self.file.flush()

    def writelines(self, lines):
        for line in lines:
            self.write(line)
