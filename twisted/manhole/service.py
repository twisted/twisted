from twisted.spread import pb

from cStringIO import StringIO

import sys

import traceback

class Perspective(pb.Perspective):
    def __init__(self):
        self.namespace = {}
    def perspective_do(self, mesg):
        fn = "$manhole"
        rtval = ""
        try:
            code = compile(mesg, fn, 'eval')
        except:
            try:
                code = compile(mesg, fn, 'exec')
            except:
                io = StringIO()
                traceback.print_exc(file=io)
                return io.getvalue()
        try:
            out = sys.stdout
            sys.stdout = StringIO()
            try:
                val = eval(code, self.namespace)
            finally:
                rtval = sys.stdout.getvalue()
                sys.stdout = out
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            return rtval + io.getvalue()

        if val is not None:
            return rtval + '\n' + repr(val)
        else:
            return rtval

class Service(pb.Service):
    # By default, "guest"/"guest" will work as login and password, though you
    # must implement something to retrieve a perspective.
    def getPerspectiveNamed(self, name):
        return Perspective()

