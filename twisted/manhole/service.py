
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

from twisted.spread import pb
from twisted.python import log

import string
from cStringIO import StringIO

import sys, copy
import traceback

class FakeStdIO:
    def __init__(self, type, list):
        self.type = type
        self.list = list

    def write(self,text):
        log.msg("%s: %s" % (self.type,string.strip(text)))
        self.list.append([self.type, text])

    def flush(self):
        pass

class Perspective(pb.Perspective):
    def perspective_do(self, mesg):
        """returns a list of ["type", "message"] pairs to the client for
        display"""
        fn = str(self.service)
        output = []
        log.msg(">>> %s" % mesg)
        fakeout = FakeStdIO("out", output)
        fakeerr = FakeStdIO("err", output)
        resfile = FakeStdIO("result", output)
        errfile = FakeStdIO("error", output)
        code = None
        try:
            try:
                code = compile(mesg, fn, 'eval')
            except:
                code = compile(mesg, fn, 'single')

            if code:
                out = sys.stdout
                err = sys.stderr
                sys.stdout = fakeout
                sys.stderr = fakeerr
                try:
                    val = eval(code, self.service.namespace)
                    if val is not None:
                        resfile.write(str(val)+'\n')
                        self.service.namespace["_"] = val
                finally:
                    sys.stdout = out
                    sys.stderr = err
        except:
            (eType, eVal, tb) = sys.exc_info()
            # Drop this frame off the traceback report.
            tb_list = traceback.extract_tb(tb)[1:]
            del tb
            # Fill in source lines from 'mesg' when we can.
            for i in xrange(len(tb_list)):
                tb_line = tb_list[i]
                (filename, lineNum, func, src) = tb_line
                if ((src == None) and (filename == fn) and (func == '?')):
                    src_lines = string.split(mesg, '\n')
                    if len(src_lines) > lineNum:
                        src = src_lines[lineNum]
                        tb_list[i] = (filename, lineNum, func, src)

            tb_list = traceback.format_list(tb_list)
            ex_list = traceback.format_exception_only(eType, eVal)
            s = string.join(tb_list + ex_list, '')
            errfile.write(s)
        log.msg("<<<")
        return output

class Service(pb.Service):
    # By default, "guest"/"guest" will work as login and password, though you
    # must implement something to retrieve a perspective.
    def __init__(self, serviceName='twisted.manhole', application=None):
        pb.Service.__init__(self, serviceName, application)
        self.namespace = {'__name__': str(self)}

    def __getstate__(self):
        """This returns the persistent state of this shell factory.
        """
        # TODO -- refactor this and twisted.reality.author.Author to use common
        # functionality (perhaps the 'code' module?)
        dict = self.__dict__
        ns = copy.copy(dict['namespace'])
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict

    def getPerspectiveNamed(self, name):
        return Perspective(name, self)

    def __str__(self):
        s = "<%s in application \'%s\'>" % (self.serviceName,
                                                    self.application.name)
        return s
