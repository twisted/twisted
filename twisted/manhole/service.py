from twisted.spread import pb

import string
from cStringIO import StringIO

import sys

import traceback

class FakeStdIO:
    def __init__(self, type, list):
        self.type = type
        self.list = list

    def write(self,text):
        self.list.append([self.type, text])

    def flush(self): 
        pass

class Perspective(pb.Perspective):
    def __init__(self):
        self.namespace = {}
    def perspective_do(self, mesg):
        """returns a list of ["type", "message"] pairs to the client for
        display"""
        fn = "$manhole"
        output = []
        try:
            code = compile(mesg, fn, 'eval')
        except:
            try:
                code = compile(mesg, fn, 'exec')
            except:
                io = StringIO()
                traceback.print_exc(file=io)
                return ["error", io.getvalue()]
        try:
            out = sys.stdout
            err = sys.stderr
            sys.stdout = FakeStdIO("out", output)
            sys.stderr = FakeStdIO("err", output)
            try:
                val = eval(code, self.namespace)
                if val is not None:
                    output.append(["result", str(val)])
            finally:
                sys.stdout = out
                sys.stderr = err
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            output.append(["error", io.getvalue()])
            return output

        return output

class Service(pb.Service):
    # By default, "guest"/"guest" will work as login and password, though you
    # must implement something to retrieve a perspective.
    def getPerspectiveNamed(self, name):
        return Perspective()

