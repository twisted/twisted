
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""L{twisted.manhole} L{PB<twisted.spread.pb>} service implementation.
"""

# twisted imports
from twisted import copyright
from twisted.spread import pb
from twisted.python import log, failure
from twisted.cred import portal
from twisted.application import service
from zope.interface import implements, Interface

# sibling imports
import explorer

import string
import sys
import traceback


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


class IManholeClient(Interface):
    def console(list_of_messages):
        """Takes a list of (type, message) pairs to display.

        Types include:
            - \"stdout\" -- string sent to sys.stdout

            - \"stderr\" -- string sent to sys.stderr

            - \"result\" -- string repr of the resulting value
                 of the expression

            - \"exception\" -- a L{failure.Failure}
        """

    def receiveExplorer(xplorer):
        """Receives an explorer.Explorer
        """

    def listCapabilities():
        """List what manholey things I am capable of doing.

        i.e. C{\"Explorer\"}, C{\"Failure\"}
        """

def runInConsole(command, console, globalNS=None, localNS=None,
                 filename=None, args=None, kw=None, unsafeTracebacks=False):
    """Run this, directing all output to the specified console.

    If command is callable, it will be called with the args and keywords
    provided.  Otherwise, command will be compiled and eval'd.
    (Wouldn't you like a macro?)

    Returns the command's return value.

    The console is called with a list of (type, message) pairs for
    display, see L{IManholeClient.console}.
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
    if (globalNS is None) and (not callable(command)):
        raise ValueError("Need a namespace to evaluate the command in.")

    try:
        out = sys.stdout
        err = sys.stderr
        sys.stdout = fakeout
        sys.stderr = fakeerr
        try:
            if callable(command):
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
        fail = failure.Failure(eVal, eType, tb)
        del tb
        # In CVS reversion 1.35, there was some code here to fill in the
        # source lines in the traceback for frames in the local command
        # buffer.  But I can't figure out when that's triggered, so it's
        # going away in the conversion to Failure, until you bring it back.
        errfile.write(pb.failure2Copyable(fail, unsafeTracebacks))

    if console:
        fakeout.consolidate()
        console(output)

    return val

def _failureOldStyle(fail):
    """Pre-Failure manhole representation of exceptions.

    For compatibility with manhole clients without the \"Failure\"
    capability.

    A dictionary with two members:
        - \'traceback\' -- traceback.extract_tb output; a list of tuples
             (filename, line number, function name, text) suitable for
             feeding to traceback.format_list.

        - \'exception\' -- a list of one or more strings, each
             ending in a newline. (traceback.format_exception_only output)
    """
    import linecache
    tb = []
    for f in fail.frames:
        # (filename, line number, function name, text)
        tb.append((f[1], f[2], f[0], linecache.getline(f[1], f[2])))

    return {
        'traceback': tb,
        'exception': traceback.format_exception_only(fail.type, fail.value)
        }

# Capabilities clients are likely to have before they knew how to answer a
# "listCapabilities" query.
_defaultCapabilities = {
    "Explorer": 'Set'
    }

class Perspective(pb.Avatar):
    lastDeferred = 0
    def __init__(self, service):
        self.localNamespace = {
            "service": service,
            "avatar": self,
            "_": None,
            }
        self.clients = {}
        self.service = service

    def __getstate__(self):
        state = self.__dict__.copy()
        state['clients'] = {}
        if state['localNamespace'].has_key("__builtins__"):
            del state['localNamespace']['__builtins__']
        return state

    def attached(self, client, identity):
        """A client has attached -- welcome them and add them to the list.
        """
        self.clients[client] = identity

        host = ':'.join(map(str, client.broker.transport.getHost()[1:]))

        msg = self.service.welcomeMessage % {
            'you': getattr(identity, 'name', str(identity)),
            'host': host,
            'longversion': copyright.longversion,
            }

        client.callRemote('console', [("stdout", msg)])

        client.capabilities = _defaultCapabilities
        client.callRemote('listCapabilities').addCallbacks(
            self._cbClientCapable, self._ebClientCapable,
            callbackArgs=(client,),errbackArgs=(client,))

    def detached(self, client, identity):
        try:
            del self.clients[client]
        except KeyError:
            pass

    def runInConsole(self, command, *args, **kw):
        """Convience method to \"runInConsole with my stuff\".
        """
        return runInConsole(command,
                            self.console,
                            self.service.namespace,
                            self.localNamespace,
                            str(self.service),
                            args=args,
                            kw=kw,
                            unsafeTracebacks=self.service.unsafeTracebacks)


    ### Methods for communicating to my clients.

    def console(self, message):
        """Pass a message to my clients' console.
        """
        clients = self.clients.keys()
        origMessage = message
        compatMessage = None
        for client in clients:
            try:
                if "Failure" not in client.capabilities:
                    if compatMessage is None:
                        compatMessage = origMessage[:]
                        for i in xrange(len(message)):
                            if ((message[i][0] == "exception") and
                                isinstance(message[i][1], failure.Failure)):
                                compatMessage[i] = (
                                    message[i][0],
                                    _failureOldStyle(message[i][1]))
                    client.callRemote('console', compatMessage)
                else:
                    client.callRemote('console', message)
            except pb.ProtocolError:
                # Stale broker.
                self.detached(client, None)

    def receiveExplorer(self, objectLink):
        """Pass an Explorer on to my clients.
        """
        clients = self.clients.keys()
        for client in clients:
            try:
                client.callRemote('receiveExplorer', objectLink)
            except pb.ProtocolError:
                # Stale broker.
                self.detached(client, None)


    def _cbResult(self, val, dnum):
        self.console([('result', "Deferred #%s Result: %r\n" %(dnum, val))])
        return val

    def _cbClientCapable(self, capabilities, client):
        log.msg("client %x has %s" % (id(client), capabilities))
        client.capabilities = capabilities

    def _ebClientCapable(self, reason, client):
        reason.trap(AttributeError)
        log.msg("Couldn't get capabilities from %s, assuming defaults." %
                (client,))

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
            from twisted.internet.defer import Deferred
            # TODO: client support for Deferred.
            if isinstance(val, Deferred):
                self.lastDeferred += 1
                self.console([('result', "Waiting for Deferred #%s...\n" % self.lastDeferred)])
                val.addBoth(self._cbResult, self.lastDeferred)
            else:
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


class Realm:

    implements(portal.IRealm)

    def __init__(self, service):
        self.service = service
        self._cache = {}

    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective not in interfaces:
            raise NotImplementedError("no interface")
        if avatarId in self._cache:
            p = self._cache[avatarId]
        else:
            p = Perspective(self.service)
        p.attached(mind, avatarId)
        def detached():
            p.detached(mind, avatarId)
        return (pb.IPerspective, p, detached)


class Service(service.Service):

    welcomeMessage = (
        "\nHello %(you)s, welcome to Manhole "
        "on %(host)s.\n"
        "%(longversion)s.\n\n")

    def __init__(self, unsafeTracebacks=False, namespace=None):
        self.unsafeTracebacks = unsafeTracebacks
        self.namespace = {
            '__name__': '__manhole%x__' % (id(self),),
            'sys': sys
            }
        if namespace:
            self.namespace.update(namespace)

    def __getstate__(self):
        """This returns the persistent state of this shell factory.
        """
        # TODO -- refactor this and twisted.reality.author.Author to
        # use common functionality (perhaps the 'code' module?)
        dict = self.__dict__.copy()
        ns = dict['namespace'].copy()
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict
