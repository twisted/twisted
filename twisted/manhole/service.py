
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

# twisted imports
from twisted import copyright

from twisted.spread import pb
from twisted.python import explorer, log

# sibling imports
import coil

# system imports
from cStringIO import StringIO

import copy
import operator
import string
import sys
import traceback
import types


class FakeStdIO:
    def __init__(self, type_, list):
        self.type = type_
        self.list = list

    def write(self, text):
        log.msg("%s: %s" % (self.type, string.strip(str(text))))
        self.list.append((self.type, text))

    def flush(self):
        pass

    def consolidate(self):
        """Concatenate adjacent messages of same type into one.

        Greatly cuts down on the number of elements, increasing
        network transport friendliness considerably.
        """
        if not self.list:
            return

        inlist = self.list
        outlist = []
        last_type = inlist[0]
        block_begin = 0
        for i in xrange(1, len(self.list)):
            (mtype, message) = inlist[i]
            if mtype == last_type:
                continue
            else:
                if (i - block_begin) == 1:
                    outlist.append(inlist[block_begin])
                else:
                    messages = map(lambda l: l[1],
                                   inlist[block_begin:i])
                    message = string.join(messages, '')
                    outlist.append((last_type, message))
                last_type = mtype
                block_begin = i


class ManholeClientInterface:
    def console(self, list_of_messages):
        """Takes a list of (type, message) pairs to display.

        Types include:
            \"stdout\" -- string sent to sys.stdout

            \"stderr\" -- string sent to sys.stderr

            \"result\" -- string repr of the resulting value
                 of the expression

            \"exception\" -- a dictionary with two members:
                \'traceback\' -- traceback.extract_tb output; a list of
                     tuples (filename, line number, function name, text)
                     suitable for feeding to traceback.format_list.

                \'exception\' -- a list of one or more strings, each
                     ending in a newline.
                     (traceback.format_exception_only output)
        """

    def receiveExplorer(self, xplorer):
        """Receives an explorer.Explorer
        """

def runInConsole(command, console, globalNS=None, localNS=None,
                 filename=None, args=None, kw=None):
    """Run this, directing all output to the specified console.

    If command is callable, it will be called with the args and keywords
    provided.  Otherwise, command will be compiled and eval'd.
    (Wouldn't you like a macro?)

    Returns the command's return value.

    The console is called with a list of (type, message) pairs for
    display, see ManholeClientInterface.console.
    """
    output = []
    fakeout = FakeStdIO("stdout", output)
    fakeerr = FakeStdIO("stderr", output)
    errfile = FakeStdIO("exception", output)
    code = None
    val = None
    if filename is None:
        filename = str(console)
    if args is None:
        args = ()
    if kw is None:
        kw = {}
    if localNS is None:
        localNS = globalNS
    if (globalNS is None) and (not operator.isCallable(command)):
        raise ValueError("Need a namespace to evaluate the command in.")

    try:
        out = sys.stdout
        err = sys.stderr
        sys.stdout = fakeout
        sys.stderr = fakeerr
        try:
            if operator.isCallable(command):
                val = apply(command, args, kw)
            else:
                try:
                    code = compile(command, filename, 'eval')
                except:
                    code = compile(command, filename, 'single')

                if code:
                    val = eval(code, globalNS, localNS)
        finally:
            sys.stdout = out
            sys.stderr = err
    except:
        (eType, eVal, tb) = sys.exc_info()
        tb_list = traceback.extract_tb(tb)[1:]
        del tb
        if not operator.isCallable(command):
            # Fill in source lines from 'command' when we can.
            for i in xrange(len(tb_list)):
                tb_line = tb_list[i]
                (filename_, lineNum, func, src) = tb_line
                if ((src == None)
                    and (filename_ == filename)
                    and (func == '?')):

                    src_lines = string.split(str(command), '\n')
                    if len(src_lines) > lineNum:
                        src = src_lines[lineNum]
                        tb_list[i] = (filename_, lineNum, func, src)

        ex_list = traceback.format_exception_only(eType, eVal)
        errfile.write({'traceback': tb_list,
                       'exception': ex_list})

    if console:
        fakeout.consolidate()
        console(output)

    return val


class Perspective(pb.Perspective):
    def __init__(self, perspectiveName, identityName="Nobody"):
        pb.Perspective.__init__(self, perspectiveName, identityName)
        self.localNamespace = {
            "_": None,
            }
        self.clients = {}

    def __getstate__(self):
        state = self.__dict__.copy()
        state['clients'] = {}
        if state['localNamespace'].has_key("__builtins__"):
            del state['localNamespace']['__builtins__']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        ### Aw shucks.  This don't work 'cuz I get unpickled before
        ### my service does.
        ## self.browser.globalNamespace = self.service.namespace
        ## self.browser.localNamespace = self.localNamespace

    def setService(self, service):
        pb.Perspective.setService(self, service)
        # self.browser.globalNamespace = service.namespace

    def attached(self, client, identity):
        """A client has attached -- welcome them and add them to the list.
        """
        self.clients[client] = identity

        msg = self.service.welcomeMessage % {
            'you': getattr(identity, 'name', str(identity)),
            'serviceName': self.service.getServiceName(),
            'app': getattr(self.service.application, 'name',
                           "some application"),
            'host': 'some computer somewhere',
            'longversion': copyright.longversion,
            }

        client.console([("stdout", msg)])

        return pb.Perspective.attached(self, client, identity)

    def detached(self, client, identity):
        try:
            del self.clients[client]
        except KeyError:
            pass

        return pb.Perspective.detached(self, client, identity)

    def runInConsole(self, command, *args, **kw):
        """Convience method to \"runInConsole with my stuff\".
        """
        return runInConsole(command,
                            self.console,
                            self.service.namespace,
                            self.localNamespace,
                            str(self.service),
                            args=args,
                            kw=kw)


    ### Methods for communicating to my clients.

    def console(self, message):
        """Pass a message to my clients' console.
        """
        clients = self.clients.keys()
        for client in clients:
            try:
                client.console(message)
            except pb.ProtocolError:
                # Stale broker.
                self.detached(client, None)

    def receiveExplorer(self, objectLink):
        """Pass an Explorer on to my clients.
        """
        clients = self.clients.keys()
        for client in clients:
            try:
                client.receiveExplorer(objectLink)
            except pb.ProtocolError:
                # Stale broker.
                self.detached(client, None)


    ### perspective_ methods, commands used by the client.

    def perspective_do(self, expr):
        """Evaluate the given expression, with output to the console.

        The result is stored in the local variable '_', and its repr()
        string is sent to the console as a \"result\" message.
        """
        log.msg(">>> %s" % expr)
        val = self.runInConsole(expr)
        if val is not None:
            self.localNamespace["_"] = val
            self.console([("result", repr(val) + '\n')])
        log.msg("<<<")

    def perspective_explore(self, identifier):
        """Browse the object obtained by evaluating the identifier.

        The resulting ObjectLink is passed back through the client's
        receiveBrowserObject method.
        """
        object = self.runInConsole(identifier)
        if object:
            expl = explorer.explorerPool.getExplorer(object, identifier)
            self.receiveExplorer(expl)

    def perspective_watch(self, identifier):
        """Watch the object obtained by evaluating the identifier.

        Whenever I think this object might have changed, I will pass
        an ObjectLink of it back to the client's receiveBrowserObject
        method.
        """
        raise NotImplementedError
        object = self.runInConsole(identifier)
        if object:
            # Return an ObjectLink of this right away, before the watch.
            oLink = self.runInConsole(self.browser.browseObject,
                                      object, identifier)
            self.receiveExplorer(oLink)

            self.runInConsole(self.browser.watchObject,
                              object, identifier,
                              self.receiveExplorer)


class Service(pb.Service, coil.Configurable):
    perspectiveClass = Perspective
    serviceType = "manhole"

    welcomeMessage = (
        "\nHello %(you)s, welcome to %(serviceName)s "
        "in %(app)s on %(host)s.\n"
        "%(longversion)s.\n\n")

    def __init__(self, serviceName='twisted.manhole', application=None):
        pb.Service.__init__(self, serviceName, application)

        self.namespace = {
            # I'd specify __name__ so we don't get it from __builtins__,
            # but that seems to have the potential for breaking imports.
            '__name__': '__manhole%x__' % (id(self),),
            # sys, so sys.modules will be readily available
            'sys': sys
            }

    def __getstate__(self):
        """This returns the persistent state of this shell factory.
        """
        # TODO -- refactor this and twisted.reality.author.Author to
        # use common functionality (perhaps the 'code' module?)
        dict = self.__dict__
        ns = copy.copy(dict['namespace'])
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict

    def __str__(self):
        s = "<%s in application \'%s\'>" % (self.getServiceName(),
                                            getattr(self.application,
                                                    'name', "???"))
        return s

    # Config interfaces for coil
    def configInit(self, container, name):
        self.__init__(name, container.app)

    def getConfiguration(self):
        return {"name": self.serviceName}

    configTypes = {
        'name': types.StringType
        }

    configName = 'Twisted Manhole PB Service'

    def config_name(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")


coil.registerClass(Service)