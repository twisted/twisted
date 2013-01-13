# -*- test-case-name: twisted.protocols.test.test_memcache -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Memcache client protocol. Memcached is a caching server, storing data in the
form of pairs key/value, and memcache is the protocol to talk with it.

To connect to a server, create a factory for L{MemCacheProtocol}::

    from twisted.internet import reactor, protocol
    from twisted.protocols.memcache import MemCacheProtocol, DEFAULT_PORT
    d = protocol.ClientCreator(reactor, MemCacheProtocol
        ).connectTCP("localhost", DEFAULT_PORT)
    def doSomething(proto):
        # Here you call the memcache operations
        return proto.set("mykey", "a lot of data")
    d.addCallback(doSomething)
    reactor.run()

All the operations of the memcache protocol are present, but
L{MemCacheProtocol.set} and L{MemCacheProtocol.get} are the more important.
"""

import struct

from collections import deque


from twisted.protocols.basic import LineReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.internet.defer import Deferred, fail, TimeoutError
from twisted.internet.protocol import Protocol
from twisted.python import log



DEFAULT_PORT = 11211



class NoSuchCommand(Exception):
    """
    Exception raised when a non existent command is called.
    """



class ClientError(Exception):
    """
    Error caused by an invalid client call.
    """



class ServerError(Exception):
    """
    Problem happening on the server.
    """



class Command(object):
    """
    Wrap a client action into an object, that holds the values used in the
    protocol.

    @ivar _deferred: The L{Deferred} object that will be fired when the result
        arrives.
    @type _deferred: L{Deferred}

    @ivar command: Name of the command sent to the server.
    @type command: C{str}
    """

    def __init__(self, command, **kwargs):
        """
        Create a command.

        @param command: The name of the command.
        @type command: C{str}

        @param kwargs: This values will be stored as attributes of the object
            for future use
        """
        self.command = command
        self._deferred = Deferred()
        for k, v in kwargs.items():
            setattr(self, k, v)


    def success(self, value):
        """
        Shortcut method to fire the underlying deferred.
        """
        self._deferred.callback(value)


    def fail(self, error):
        """
        Make the underlying deferred fails.
        """
        self._deferred.errback(error)



class MemCacheProtocol(LineReceiver, TimeoutMixin):
    """
    MemCache protocol: connect to a memcached server to store/retrieve values.

    @ivar persistentTimeOut: The timeout period used to wait for a response.
    @type persistentTimeOut: C{int}

    @ivar _current: Current list of requests waiting for an answer from the
        server.
    @type _current: C{deque} of L{Command}

    @ivar _lenExpected: Amount of data expected in raw mode, when reading for
        a value.
    @type _lenExpected: C{int}

    @ivar _getBuffer: Current buffer of data, used to store temporary data
        when reading in raw mode.
    @type _getBuffer: C{list}

    @ivar _bufferLength: The total amount of bytes in C{_getBuffer}.
    @type _bufferLength: C{int}

    @ivar _disconnected: Indicate if the connectionLost has been called or not.
    @type _disconnected: C{bool}
    """
    MAX_KEY_LENGTH = 250
    _disconnected = False

    def __init__(self, timeOut=60):
        """
        Create the protocol.

        @param timeOut: The timeout to wait before detecting that the
            connection is dead and close it. It's expressed in seconds.
        @type timeOut: C{int}
        """
        self._current = deque()
        self._lenExpected = None
        self._getBuffer = None
        self._bufferLength = None
        self.persistentTimeOut = self.timeOut = timeOut


    def _cancelCommands(self, reason):
        """
        Cancel all the outstanding commands, making them fail with C{reason}.
        """
        while self._current:
            cmd = self._current.popleft()
            cmd.fail(reason)


    def timeoutConnection(self):
        """
        Close the connection in case of timeout.
        """
        self._cancelCommands(TimeoutError("Connection timeout"))
        self.transport.loseConnection()


    def connectionLost(self, reason):
        """
        Cause any outstanding commands to fail.
        """
        self._disconnected = True
        self._cancelCommands(reason)
        LineReceiver.connectionLost(self, reason)


    def sendLine(self, line):
        """
        Override sendLine to add a timeout to response.
        """
        if not self._current:
            self.setTimeout(self.persistentTimeOut)
        LineReceiver.sendLine(self, line)


    def rawDataReceived(self, data):
        """
        Collect data for a get.
        """
        self.resetTimeout()
        self._getBuffer.append(data)
        self._bufferLength += len(data)
        if self._bufferLength >= self._lenExpected + 2:
            data = "".join(self._getBuffer)
            buf = data[:self._lenExpected]
            rem = data[self._lenExpected + 2:]
            val = buf
            self._lenExpected = None
            self._getBuffer = None
            self._bufferLength = None
            cmd = self._current[0]
            if cmd.multiple:
                flags, cas = cmd.values[cmd.currentKey]
                cmd.values[cmd.currentKey] = (flags, cas, val)
            else:
                cmd.value = val
            self.setLineMode(rem)


    def cmd_STORED(self):
        """
        Manage a success response to a set operation.
        """
        self._current.popleft().success(True)


    def cmd_NOT_STORED(self):
        """
        Manage a specific 'not stored' response to a set operation: this is not
        an error, but some condition wasn't met.
        """
        self._current.popleft().success(False)


    def cmd_END(self):
        """
        This the end token to a get or a stat operation.
        """
        cmd = self._current.popleft()
        if cmd.command == "get":
            if cmd.multiple:
                values = dict([(key, val[::2]) for key, val in
                               cmd.values.iteritems()])
                cmd.success(values)
            else:
                cmd.success((cmd.flags, cmd.value))
        elif cmd.command == "gets":
            if cmd.multiple:
                cmd.success(cmd.values)
            else:
                cmd.success((cmd.flags, cmd.cas, cmd.value))
        elif cmd.command == "stats":
            cmd.success(cmd.values)


    def cmd_NOT_FOUND(self):
        """
        Manage error response for incr/decr/delete.
        """
        self._current.popleft().success(False)


    def cmd_VALUE(self, line):
        """
        Prepare the reading a value after a get.
        """
        cmd = self._current[0]
        if cmd.command == "get":
            key, flags, length = line.split()
            cas = ""
        else:
            key, flags, length, cas = line.split()
        self._lenExpected = int(length)
        self._getBuffer = []
        self._bufferLength = 0
        if cmd.multiple:
            if key not in cmd.keys:
                raise RuntimeError("Unexpected commands answer.")
            cmd.currentKey = key
            cmd.values[key] = [int(flags), cas]
        else:
            if cmd.key != key:
                raise RuntimeError("Unexpected commands answer.")
            cmd.flags = int(flags)
            cmd.cas = cas
        self.setRawMode()


    def cmd_STAT(self, line):
        """
        Reception of one stat line.
        """
        cmd = self._current[0]
        key, val = line.split(" ", 1)
        cmd.values[key] = val


    def cmd_VERSION(self, versionData):
        """
        Read version token.
        """
        self._current.popleft().success(versionData)


    def cmd_ERROR(self):
        """
        An non-existent command has been sent.
        """
        log.err("Non-existent command sent.")
        cmd = self._current.popleft()
        cmd.fail(NoSuchCommand())


    def cmd_CLIENT_ERROR(self, errText):
        """
        An invalid input as been sent.
        """
        log.err("Invalid input: %s" % (errText,))
        cmd = self._current.popleft()
        cmd.fail(ClientError(errText))


    def cmd_SERVER_ERROR(self, errText):
        """
        An error has happened server-side.
        """
        log.err("Server error: %s" % (errText,))
        cmd = self._current.popleft()
        cmd.fail(ServerError(errText))


    def cmd_DELETED(self):
        """
        A delete command has completed successfully.
        """
        self._current.popleft().success(True)


    def cmd_OK(self):
        """
        The last command has been completed.
        """
        self._current.popleft().success(True)


    def cmd_EXISTS(self):
        """
        A C{checkAndSet} update has failed.
        """
        self._current.popleft().success(False)


    def lineReceived(self, line):
        """
        Receive line commands from the server.
        """
        self.resetTimeout()
        token = line.split(" ", 1)[0]
        # First manage standard commands without space
        cmd = getattr(self, "cmd_%s" % (token,), None)
        if cmd is not None:
            args = line.split(" ", 1)[1:]
            if args:
                cmd(args[0])
            else:
                cmd()
        else:
            # Then manage commands with space in it
            line = line.replace(" ", "_")
            cmd = getattr(self, "cmd_%s" % (line,), None)
            if cmd is not None:
                cmd()
            else:
                # Increment/Decrement response
                cmd = self._current.popleft()
                val = int(line)
                cmd.success(val)
        if not self._current:
            # No pending request, remove timeout
            self.setTimeout(None)


    def increment(self, key, val=1):
        """
        Increment the value of C{key} by given value (default to 1).
        C{key} must be consistent with an int. Return the new value.

        @param key: The key to modify.
        @type key: C{str}

        @param val: The value to increment.
        @type val: C{int}

        @return: A deferred with will be called back with the new value
            associated with the key (after the increment).
        @rtype: L{Deferred}
        """
        return self._incrdecr("incr", key, val)


    def decrement(self, key, val=1):
        """
        Decrement the value of C{key} by given value (default to 1).
        C{key} must be consistent with an int. Return the new value, coerced to
        0 if negative.

        @param key: The key to modify.
        @type key: C{str}

        @param val: The value to decrement.
        @type val: C{int}

        @return: A deferred with will be called back with the new value
            associated with the key (after the decrement).
        @rtype: L{Deferred}
        """
        return self._incrdecr("decr", key, val)


    def _incrdecr(self, cmd, key, val):
        """
        Internal wrapper for incr/decr.
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        if not isinstance(key, str):
            return fail(ClientError(
                "Invalid type for key: %s, expecting a string" % (type(key),)))
        if len(key) > self.MAX_KEY_LENGTH:
            return fail(ClientError("Key too long"))
        fullcmd = "%s %s %d" % (cmd, key, int(val))
        self.sendLine(fullcmd)
        cmdObj = Command(cmd, key=key)
        self._current.append(cmdObj)
        return cmdObj._deferred


    def replace(self, key, val, flags=0, expireTime=0):
        """
        Replace the given C{key}. It must already exist in the server.

        @param key: The key to replace.
        @type key: C{str}

        @param val: The new value associated with the key.
        @type val: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, and C{False} with the key didn't previously exist.
        @rtype: L{Deferred}
        """
        return self._set("replace", key, val, flags, expireTime, "")


    def add(self, key, val, flags=0, expireTime=0):
        """
        Add the given C{key}. It must not exist in the server.

        @param key: The key to add.
        @type key: C{str}

        @param val: The value associated with the key.
        @type val: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, and C{False} with the key already exists.
        @rtype: L{Deferred}
        """
        return self._set("add", key, val, flags, expireTime, "")


    def set(self, key, val, flags=0, expireTime=0):
        """
        Set the given C{key}.

        @param key: The key to set.
        @type key: C{str}

        @param val: The value associated with the key.
        @type val: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded.
        @rtype: L{Deferred}
        """
        return self._set("set", key, val, flags, expireTime, "")


    def checkAndSet(self, key, val, cas, flags=0, expireTime=0):
        """
        Change the content of C{key} only if the C{cas} value matches the
        current one associated with the key. Use this to store a value which
        hasn't been modified since last time you fetched it.

        @param key: The key to set.
        @type key: C{str}

        @param val: The value associated with the key.
        @type val: C{str}

        @param cas: Unique 64-bit value returned by previous call of C{get}.
        @type cas: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, C{False} otherwise.
        @rtype: L{Deferred}
        """
        return self._set("cas", key, val, flags, expireTime, cas)


    def _set(self, cmd, key, val, flags, expireTime, cas):
        """
        Internal wrapper for setting values.
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        if not isinstance(key, str):
            return fail(ClientError(
                "Invalid type for key: %s, expecting a string" % (type(key),)))
        if len(key) > self.MAX_KEY_LENGTH:
            return fail(ClientError("Key too long"))
        if not isinstance(val, str):
            return fail(ClientError(
                "Invalid type for value: %s, expecting a string" %
                (type(val),)))
        if cas:
            cas = " " + cas
        length = len(val)
        fullcmd = "%s %s %d %d %d%s" % (
            cmd, key, flags, expireTime, length, cas)
        self.sendLine(fullcmd)
        self.sendLine(val)
        cmdObj = Command(cmd, key=key, flags=flags, length=length)
        self._current.append(cmdObj)
        return cmdObj._deferred


    def append(self, key, val):
        """
        Append given data to the value of an existing key.

        @param key: The key to modify.
        @type key: C{str}

        @param val: The value to append to the current value associated with
            the key.
        @type val: C{str}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, C{False} otherwise.
        @rtype: L{Deferred}
        """
        # Even if flags and expTime values are ignored, we have to pass them
        return self._set("append", key, val, 0, 0, "")


    def prepend(self, key, val):
        """
        Prepend given data to the value of an existing key.

        @param key: The key to modify.
        @type key: C{str}

        @param val: The value to prepend to the current value associated with
            the key.
        @type val: C{str}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, C{False} otherwise.
        @rtype: L{Deferred}
        """
        # Even if flags and expTime values are ignored, we have to pass them
        return self._set("prepend", key, val, 0, 0, "")


    def get(self, key, withIdentifier=False):
        """
        Get the given C{key}. It doesn't support multiple keys. If
        C{withIdentifier} is set to C{True}, the command issued is a C{gets},
        that will return the current identifier associated with the value. This
        identifier has to be used when issuing C{checkAndSet} update later,
        using the corresponding method.

        @param key: The key to retrieve.
        @type key: C{str}

        @param withIdentifier: If set to C{True}, retrieve the current
            identifier along with the value and the flags.
        @type withIdentifier: C{bool}

        @return: A deferred that will fire with the tuple (flags, value) if
            C{withIdentifier} is C{False}, or (flags, cas identifier, value)
            if C{True}.  If the server indicates there is no value
            associated with C{key}, the returned value will be C{None} and
            the returned flags will be C{0}.
        @rtype: L{Deferred}
        """
        return self._get([key], withIdentifier, False)


    def getMultiple(self, keys, withIdentifier=False):
        """
        Get the given list of C{keys}.  If C{withIdentifier} is set to C{True},
        the command issued is a C{gets}, that will return the identifiers
        associated with each values. This identifier has to be used when
        issuing C{checkAndSet} update later, using the corresponding method.

        @param keys: The keys to retrieve.
        @type keys: C{list} of C{str}

        @param withIdentifier: If set to C{True}, retrieve the identifiers
            along with the values and the flags.
        @type withIdentifier: C{bool}

        @return: A deferred that will fire with a dictionary with the elements
            of C{keys} as keys and the tuples (flags, value) as values if
            C{withIdentifier} is C{False}, or (flags, cas identifier, value) if
            C{True}.  If the server indicates there is no value associated with
            C{key}, the returned values will be C{None} and the returned flags
            will be C{0}.
        @rtype: L{Deferred}

        @since: 9.0
        """
        return self._get(keys, withIdentifier, True)

    def _get(self, keys, withIdentifier, multiple):
        """
        Helper method for C{get} and C{getMultiple}.
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        for key in keys:
            if not isinstance(key, str):
                return fail(
                    ClientError(
                        "Invalid type for key: %s, expecting a "
                        "string" % (type(key),)))
            if len(key) > self.MAX_KEY_LENGTH:
                return fail(ClientError("Key too long"))
        if withIdentifier:
            cmd = "gets"
        else:
            cmd = "get"
        fullcmd = "%s %s" % (cmd, " ".join(keys))
        self.sendLine(fullcmd)
        if multiple:
            values = dict([(key, (0, "", None)) for key in keys])
            cmdObj = Command(cmd, keys=keys, values=values, multiple=True)
        else:
            cmdObj = Command(cmd, key=keys[0], value=None, flags=0, cas="",
                             multiple=False)
        self._current.append(cmdObj)
        return cmdObj._deferred

    def stats(self, arg=None):
        """
        Get some stats from the server. It will be available as a dict.

        @param arg: An optional additional string which will be sent along
            with the I{stats} command.  The interpretation of this value by
            the server is left undefined by the memcache protocol
            specification.
        @type arg: C{NoneType} or C{str}

        @return: A deferred that will fire with a C{dict} of the available
            statistics.
        @rtype: L{Deferred}
        """
        if arg:
            cmd = "stats " + arg
        else:
            cmd = "stats"
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        self.sendLine(cmd)
        cmdObj = Command("stats", values={})
        self._current.append(cmdObj)
        return cmdObj._deferred


    def version(self):
        """
        Get the version of the server.

        @return: A deferred that will fire with the string value of the
            version.
        @rtype: L{Deferred}
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        self.sendLine("version")
        cmdObj = Command("version")
        self._current.append(cmdObj)
        return cmdObj._deferred


    def delete(self, key):
        """
        Delete an existing C{key}.

        @param key: The key to delete.
        @type key: C{str}

        @return: A deferred that will be called back with C{True} if the key
            was successfully deleted, or C{False} if not.
        @rtype: L{Deferred}
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        if not isinstance(key, str):
            return fail(ClientError(
                "Invalid type for key: %s, expecting a string" % (type(key),)))
        self.sendLine("delete %s" % key)
        cmdObj = Command("delete", key=key)
        self._current.append(cmdObj)
        return cmdObj._deferred


    def flushAll(self):
        """
        Flush all cached values.

        @return: A deferred that will be called back with C{True} when the
            operation has succeeded.
        @rtype: L{Deferred}
        """
        if self._disconnected:
            return fail(RuntimeError("not connected"))
        self.sendLine("flush_all")
        cmdObj = Command("flush_all")
        self._current.append(cmdObj)
        return cmdObj._deferred



class MemCacheBinaryProtocol(Protocol, TimeoutMixin):
    """
    MemCache binary protocol: connect to a memcached server to store/retrieve
    values.

    @cvar _headerFormat: Struct format of the protocol header.
    @type _headerFormat: C{str}

    @cvar _OPCODE_MAPPING: Map of protocol key to method suffix.
    @type _OPCODE_MAPPING: C{dict}

    @ivar persistentTimeOut: The timeout period used to wait for a response.
    @type persistentTimeOut: C{int}

    @ivar _current: Current list of requests waiting for an answer from the
        server.
    @type _current: C{deque} of L{Command}

    @ivar _buffer: Current buffer of data, used to store temporary data.
    @type _buffer: C{list}

    @ivar _bufferLength: The total amount of bytes in C{_buffer}.
    @type _bufferLength: C{int}
    """

    _headerFormat = "!BBhBBhiiq"

    _OPCODE_MAPPING = {
        0: "get",
        1: "set",
        2: "add",
        3: "replace",
        4: "delete",
        5: "increment",
        6: "decrement",
        7: "quit",
        8: "flush",
        9: "noop",
        14: "append",
        15: "prepend",
        16: "stat"}


    def __init__(self, timeOut=60):
        """
        Create the protocol.

        @param timeOut: The timeout to wait before detecting that the
            connection is dead and close it. It's expressed in seconds.
        @type timeOut: C{int}
        """
        self._current = deque()
        self.persistentTimeOut = self.timeOut = timeOut
        self._buffer = []
        self._bufferLength = 0


    def dataReceived(self, data):
        """
        Handle data, dispatching decoded content to C{_cmd_*} methods.
        """
        self.resetTimeout()
        self._buffer.append(data)
        self._bufferLength += len(data)
        while self._bufferLength >= 24:
            data = "".join(self._buffer)
            if data[0] != "\x81":
                raise RuntimeError("Wrong magic byte: %r" % (data[0],))
            _, opcode, keyLength, extraLength, _, status, length, _, cas = (
                struct.unpack(self._headerFormat, data[:24]))
            if self._bufferLength < 24 + length:
                self._buffer[:] = [data]
                return
            self._buffer[:] = [data[24 + length:]]
            self._bufferLength -= 24 + length

            extra = data[24:24 + extraLength]
            key = data[24 + extraLength:24 + extraLength + keyLength]
            value = data[24 + extraLength + keyLength: 24 + length]

            if status:
                cmd = self._current.popleft()
                cmd.fail(ServerError(value))
            else:
                method = getattr(
                    self, "_cmd_%s" % (self._OPCODE_MAPPING[opcode],))
                method(cas, extra, key, value)


    def _cmd_get(self, cas, extra, key, value):
        """
        On C{get} responses, read C{extra} data as flags and fire the
        command L{Deferred} with the tuple (flags, value).
        """
        if extra:
            flags = struct.unpack("!i", extra)[0]
        else:
            flags = 0
        cmd = self._current.popleft()
        cmd.success((flags, value))


    def _cmd_set(self, cas, extra, key, value):
        """
        On C{set} responses, fire the command L{Deferred} with the C{cas}
        value.
        """
        cmd = self._current.popleft()
        cmd.success(cas)


    _cmd_add = _cmd_set


    _cmd_replace = _cmd_set


    def _cmd_delete(self, cas, extra, key, value):
        """
        On C{delete} response, fire the command L{Deferred} with C{True}.
        """
        cmd = self._current.popleft()
        cmd.success(True)


    def _cmd_increment(self, cas, extra, key, value):
        """
        On C{increment} responses, fire the command L{Deferred} with the tuple
        (cas, value) where value is unpacked as an integer.
        """
        cmd = self._current.popleft()
        cmd.success((cas, struct.unpack("!q", value)[0]))


    _cmd_decrement = _cmd_increment


    _cmd_flush = _cmd_delete


    _cmd_noop = _cmd_delete


    _cmd_append = _cmd_delete


    _cmd_prepend = _cmd_delete


    _cmd_quit = _cmd_delete


    def _cmd_stat(self, cas, extra, key, value):
        """
        On C{stat} responses, accumulate key/value pairs until we get an empty
        response and then fire the command L{Deferred} with the C{dict}.
        """
        cmd = self._current[0]
        if not value and not key:
            self._current.popleft()
            cmd.success(cmd.values)
        else:
            cmd.values[key] = value


    def timeoutConnection(self):
        """
        Close the connection in case of timeout.
        """
        while self._current:
            cmd = self._current.popleft()
            cmd.fail(TimeoutError("Connection timeout"))
        self.transport.loseConnection()


    def _send(self, opcode, key, value="", extra="", cas=0):
        """
        Send a command, creating the request header and then appending data.
        """
        if not self._current:
            self.setTimeout(self.persistentTimeOut)
        keyLength = len(key)
        extraLength = len(extra)
        header = struct.pack(
            self._headerFormat, 128, opcode, keyLength, extraLength, 0, 0,
            extraLength + keyLength + len(value), 0, cas)
        cmd = "%s%s%s%s" % (header, extra, key, value)
        self.transport.write(cmd)


    def _buildCommand(self, opcode, **kwargs):
        """
        Create a L{Command} object for a command call, appending the list of
        current commands and return the command L{Deferred}.
        """
        cmdObj = Command(opcode, **kwargs)
        self._current.append(cmdObj)
        return cmdObj._deferred


    def get(self, key):
        """
        Get the value associated with the given C{key}.

        @param key: The key to retrieve.
        @type key: C{str}

        @return: A deferred that will fire with the tuple (flags, value).
        @rtype: L{Deferred}
        """
        self._send(0, key)
        return self._buildCommand(0, key=key)


    def stats(self, arg=""):
        """
        Get some stats from the server. It will be available as a dict.

        @param arg: An optional additional string which will be sent along
            with the I{stats} command.
        @type arg: C{str}

        @return: A deferred that will fire with a C{dict} of the available
            statistics.
        @rtype: L{Deferred}
        """
        self._send(16, arg)
        return self._buildCommand(16, values={})


    def set(self, key, value, flags=0, expireTime=0, quiet=False, cas=0):
        """
        Set the given C{key}.

        @param key: The key to set.
        @type key: C{str}

        @param value: The value associated with the key.
        @type value: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @param cas: Unique 64-bit value returned by previous call.
        @type cas: C{int}

        @return: A deferred that will fire with the C{cas} value if the
            operation has succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        extra = struct.pack("!ii", flags, expireTime)
        if quiet:
            self._send(17, key, value, extra=extra, cas=cas)
        else:
            self._send(1, key, value, extra=extra, cas=cas)
            return self._buildCommand(1, key=key)


    def add(self, key, value, flags=0, expireTime=0, quiet=False):
        """
        Add the given C{key}. It must not exist in the server.

        @param key: The key to add.
        @type key: C{str}

        @param value: The value associated with the key.
        @type value: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will fire with the C{cas} value if the
            operation has succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        extra = struct.pack("!ii", flags, expireTime)
        if quiet:
            self._send(18, key, value, extra=extra)
        else:
            self._send(2, key, value, extra=extra)
            return self._buildCommand(2, key=key)


    def replace(self, key, value, flags=0, expireTime=0, quiet=False, cas=0):
        """
        Replace the given C{key}. It must already exist in the server.

        @param key: The key to replace.
        @type key: C{str}

        @param value: The new value associated with the key.
        @type value: C{str}

        @param flags: The flags to store with the key.
        @type flags: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @param cas: Unique 64-bit value returned by previous call.
        @type cas: C{int}

        @return: A deferred that will fire with the C{cas} value if the
            operation has succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        extra = struct.pack("!ii", flags, expireTime)
        if quiet:
            self._send(19, key, value, extra=extra, cas=cas)
        else:
            self._send(3, key, value, extra=extra, cas=cas)
            return self._buildCommand(3, key=key)


    def delete(self, key, quiet=False):
        """
        Delete an existing C{key}.

        @param key: The key to delete.
        @type key: C{str}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will be called back with C{True} if the key
            was successfully deleted, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        if quiet:
            self._send(20, key)
        else:
            self._send(4, key)
            return self._buildCommand(4, key=key)


    def increment(self, key, value=1, initialValue=0, expireTime=0,
                  quiet=False):
        """
        Increment the value of C{key} by given value (default to 1).
        C{key} must be consistent with an int. Return the new value.

        @param key: The key to modify.
        @type key: C{str}

        @param value: The value to increment.
        @type value: C{int}

        @param initialValue: The starting point of the increment, if the value
            doesn't exist yet.
        @type initialValue: C{int}

        @param expireTime: If different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred with will be called back with the C{cas} value and
            the new value associated with the key (after the increment), or
            nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        extra = struct.pack("!qqi", value, initialValue, expireTime)
        if quiet:
            self._send(21, key, extra=extra)
        else:
            self._send(5, key, extra=extra)
            return self._buildCommand(5, key=key)


    def decrement(self, key, value=1, initialValue=0, expireTime=0,
                  quiet=False):
        """
        Decrement the value of C{key} by given value (default to 1).
        C{key} must be consistent with an int. Return the new value, coerced to
        0 if negative.

        @param key: The key to modify.
        @type key: C{str}

        @param value: The value to decrement.
        @type value: C{int}

        @param initialValue: The starting point of the decrement, if the value
            doesn't exist yet.
        @type initialValue: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred with will be called back with the C{cas} value and
            the new value associated with the key (after the decrement), or
            nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        extra = struct.pack("!qqi", value, initialValue, expireTime)
        if quiet:
            self._send(22, key, extra=extra)
        else:
            self._send(6, key, extra=extra)
            return self._buildCommand(6, key=key)


    def flush(self, expireTime=0, quiet=False):
        """
        Flush all cached values.

        @param expireTime: If speficified, the time in the future when the
            flush should happen.
        @type expireTime: C{int}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will be called back with C{True} when the
            operation has succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        if quiet:
            self._send(24, "", extra=struct.pack("!i", expireTime))
        else:
            self._send(8, "", extra=struct.pack("!i", expireTime))
            return self._buildCommand(8)


    def noop(self):
        """
        Send a noop command, used as a keepalive.

        @return: A deferred that will be called back with C{True}.
        @rtype: L{Deferred}.
        """
        self._send(9, "")
        return self._buildCommand(9)


    def quit(self, quiet=False):
        """
        Close the connection to the server.

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will be called back with C{True}, or nothing
            if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        if quiet:
            self._send(23, "")
        else:
            self._send(7, "")
            return self._buildCommand(7)


    def append(self, key, value, quiet=False):
        """
        Append given data to the value of an existing key.

        @param key: The key to modify.
        @type key: C{str}

        @param value: The value to append to the current value associated with
            the key.
        @type value: C{str}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        if quiet:
            self._send(25, key, value)
        else:
            self._send(14, key, value)
            return self._buildCommand(14, key=key)


    def prepend(self, key, value, quiet=False):
        """
        Prepend given data to the value of an existing key.

        @param key: The key to modify.
        @type key: C{str}

        @param value: The value to prepend to the current value associated with
            the key.
        @type value: C{str}

        @param quiet: If C{True}, don't wait for a response.
        @type quiet: C{bool}

        @return: A deferred that will fire with C{True} if the operation has
            succeeded, or nothing if C{quiet} is set.
        @rtype: L{Deferred} or C{NoneType}
        """
        if quiet:
            self._send(26, key, value)
        else:
            self._send(15, key, value)
            return self._buildCommand(15, key=key)



__all__ = ["MemCacheProtocol", "DEFAULT_PORT", "NoSuchCommand", "ClientError",
           "ServerError", "MemCacheBinaryProtocol"]
