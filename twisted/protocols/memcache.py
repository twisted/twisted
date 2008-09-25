# -*- test-case-name: twisted.test.test_memcache -*-
# Copyright (c) 2007 Twisted Matrix Laboratories.
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

See U{http://code.sixapart.com/svn/memcached/trunk/server/doc/protocol.txt} for
more information about the protocol.
"""

try:
    from collections import deque
except ImportError:
    class deque(list):
        def popleft(self):
            return self.pop(0)


from zope.interface import Interface, implements

from twisted.protocols.basic import LineReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.internet.defer import Deferred, fail, TimeoutError, succeed
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

    @ivar _deferred: the L{Deferred} object that will be fired when the result
        arrives.
    @type _deferred: L{Deferred}

    @ivar command: name of the command sent to the server.
    @type command: C{str}
    """

    def __init__(self, command, **kwargs):
        """
        Create a command.

        @param command: the name of the command.
        @type command: C{str}

        @param kwargs: this values will be stored as attributes of the object
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

    @ivar persistentTimeOut: the timeout period used to wait for a response.
    @type persistentTimeOut: C{int}

    @ivar _current: current list of requests waiting for an answer from the
        server.
    @type _current: C{deque} of L{Command}

    @ivar _lenExpected: amount of data expected in raw mode, when reading for
        a value.
    @type _lenExpected: C{int}

    @ivar _getBuffer: current buffer of data, used to store temporary data
        when reading in raw mode.
    @type _getBuffer: C{list}

    @ivar _bufferLength: the total amount of bytes in C{_getBuffer}.
    @type _bufferLength: C{int}
    """
    MAX_KEY_LENGTH = 250

    def __init__(self, timeOut=60):
        """
        Create the protocol.

        @param timeOut: the timeout to wait before detecting that the
            connection is dead and close it. It's expressed in seconds.
        @type timeOut: C{int}
        """
        self._current = deque()
        self._lenExpected = None
        self._getBuffer = None
        self._bufferLength = None
        self.persistentTimeOut = self.timeOut = timeOut


    def timeoutConnection(self):
        """
        Close the connection in case of timeout.
        """
        for cmd in self._current:
            cmd.fail(TimeoutError("Connection timeout"))
        self.transport.loseConnection()


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
            cmd.success((cmd.flags, cmd.value))
        elif cmd.command == "gets":
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
        if cmd.key != key:
            raise RuntimeError("Unexpected commands answer.")
        cmd.flags = int(flags)
        cmd.length = self._lenExpected
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

        @param key: the key to modify.
        @type key: C{str}

        @param val: the value to increment.
        @type val: C{int}

        @return: a deferred with will be called back with the new value
            associated with the key (after the increment).
        @rtype: L{Deferred}
        """
        return self._incrdecr("incr", key, val)


    def decrement(self, key, val=1):
        """
        Decrement the value of C{key} by given value (default to 1).
        C{key} must be consistent with an int. Return the new value, coerced to
        0 if negative.

        @param key: the key to modify.
        @type key: C{str}

        @param val: the value to decrement.
        @type val: C{int}

        @return: a deferred with will be called back with the new value
            associated with the key (after the decrement).
        @rtype: L{Deferred}
        """
        return self._incrdecr("decr", key, val)


    def _incrdecr(self, cmd, key, val):
        """
        Internal wrapper for incr/decr.
        """
        if not isinstance(key, str):
            return fail(ClientError(
                "Invalid type for key: %s, expecting a string" % (type(key),)))
        if len(key) > self.MAX_KEY_LENGTH:
            return fail(ClientError("Key too long"))
        fullcmd = "%s %s %d" % (cmd, key, int(val))
        cmdObj = Command(cmd, key=key)
        self._current.append(cmdObj)
        self.sendLine(fullcmd)
        return cmdObj._deferred


    def replace(self, key, val, flags=0, expireTime=0):
        """
        Replace the given C{key}. It must already exist in the server.

        @param key: the key to replace.
        @type key: C{str}

        @param val: the new value associated with the key.
        @type val: C{str}

        @param flags: the flags to store with the key.
        @type flags: C{int}

        @param expireTime: if different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: a deferred that will fire with C{True} if the operation has
            succeeded, and C{False} with the key didn't previously exist.
        @rtype: L{Deferred}
        """
        return self._set("replace", key, val, flags, expireTime, "")


    def add(self, key, val, flags=0, expireTime=0):
        """
        Add the given C{key}. It must not exist in the server.

        @param key: the key to add.
        @type key: C{str}

        @param val: the value associated with the key.
        @type val: C{str}

        @param flags: the flags to store with the key.
        @type flags: C{int}

        @param expireTime: if different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: a deferred that will fire with C{True} if the operation has
            succeeded, and C{False} with the key already exists.
        @rtype: L{Deferred}
        """
        return self._set("add", key, val, flags, expireTime, "")


    def set(self, key, val, flags=0, expireTime=0):
        """
        Set the given C{key}.

        @param key: the key to set.
        @type key: C{str}

        @param val: the value associated with the key.
        @type val: C{str}

        @param flags: the flags to store with the key.
        @type flags: C{int}

        @param expireTime: if different from 0, the relative time in seconds
            when the key will be deleted from the store.
        @type expireTime: C{int}

        @return: a deferred that will fire with C{True} if the operation has
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
            if C{True}.
        @rtype: L{Deferred}
        """
        if not isinstance(key, str):
            return fail(ClientError(
                "Invalid type for key: %s, expecting a string" % (type(key),)))
        if len(key) > self.MAX_KEY_LENGTH:
            return fail(ClientError("Key too long"))
        if withIdentifier:
            cmd = "gets"
        else:
            cmd = "get"
        fullcmd = "%s %s" % (cmd, key)
        self.sendLine(fullcmd)
        cmdObj = Command(cmd, key=key, value=None, flags=0, cas="")
        self._current.append(cmdObj)
        return cmdObj._deferred


    def stats(self):
        """
        Get some stats from the server. It will be available as a dict.

        @return: a deferred that will fire with a C{dict} of the available
            statistics.
        @rtype: L{Deferred}
        """
        self.sendLine("stats")
        cmdObj = Command("stats", values={})
        self._current.append(cmdObj)
        return cmdObj._deferred


    def version(self):
        """
        Get the version of the server.

        @return: a deferred that will fire with the string value of the
            version.
        @rtype: L{Deferred}
        """
        self.sendLine("version")
        cmdObj = Command("version")
        self._current.append(cmdObj)
        return cmdObj._deferred


    def delete(self, key):
        """
        Delete an existing C{key}.

        @param key: the key to delete.
        @type key: C{str}

        @return: a deferred that will be called back with C{True} if the key
            was successfully deleted, or C{False} if not.
        @rtype: L{Deferred}
        """
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

        @return: a deferred that will be called back with C{True} when the
            operation has succeeded.
        @rtype: L{Deferred}
        """
        self.sendLine("flush_all")
        cmdObj = Command("flush_all")
        self._current.append(cmdObj)
        return cmdObj._deferred



class ICacheBackend(Interface):
    """
    Represent the set of operations needed to implement a cache backend for
    a memcache server.
    """

    def get(key):
        """
        Get a value from the cache.

        @param key: the key holding the data.
        @type key: C{str}

        @return: a deferred that will fire with the flags and the value
            associated with the key.
        @rtype: L{Deferred}
        """

    def gets(key):
        """
        Get a value from the cache.

        @param key: the key holding the data.
        @type key: C{str}

        @return: a deferred that will fire with the flags, casvalue and value
            associated with the key.
        @rtype: L{Deferred}
        """


    def set(key, value, flags, expireTime):
        """
        Set a value in the cache.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def add(key, value, flags, expireTime):
        """
        Add a value in the cache. The key must not be present in the cache.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def replace(key, value, flags, expireTime):
        """
        Replace a value in the cache. The key must be present in the cache.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def append(key, value, flags, expireTime):
        """
        Append data to a existing value in the cache. The key must be present
        in the cache. The flags and expireTime parameters are ignored.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def prepend(key, value, flags, expireTime):
        """
        Prepend data to a existing value in the cache. The key must be present
        in the cache. The flags and expireTime parameters are ignored.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def checkAndSet(key, value, flags, expireTime, casValue):
        """
        Set the value associated with key, only if the casValue is matching the
        current casValue of the key.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def delete(key):
        """
        Remove a key from the cache.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def increment(key, value):
        """
        Increment the current value associated with a key.

        @return: a deferred that will fire with the new value.
        @rtype: L{Deferred}
        """


    def decrement(key, value):
        """
        Decrement the current value associated with a key.

        @return: a deferred that will fire with the new value.
        @rtype: L{Deferred}
        """


    def flush_all():
        """
        Remove all the keys from the cache.

        @return: a deferred that will fire with C{True} if everything went
            fine.
        @rtype: L{Deferred}
        """


    def stats():
        """
        Return the statistics registered for the cache.

        @return: a deferred that will fire with a dictionary of statistics.
        @rtype: L{Deferred}
        """


    def version():
        """
        Return the version of the cache backend.

        @return: a deferred that will fire with the current version as a
            string.
        @rtype: L{Deferred}
        """



class _CachedValue(object):
    """
    Represent a value stored in a cache.
    """

    def __init__(self, value, flags, expireTime):
        """
        """
        self.value = value
        self.flags = flags
        self.expireTime = expireTime
        self.casValue = str(id(self))



class KeyNotFoundError(Exception):
    """
    Exception raised when a key hasn't been found in the cache whereas it was
    expected.
    """



class KeyFoundError(Exception):
    """
    Exception raised when a key has been found in the cache whereas it wasn't
    expected.
    """



class CasError(Exception):
    """
    Exception raised when a cas update failed because cas value has changed.
    """



class StandardBackend(object):
    """
    Simple backend using a dictionary to store values.
    """
    implements(ICacheBackend)

    def __init__(self, maxSize=0):
        """
        @param maxSize: maximum value in bytes the values in the cache should
            take. Default to 0 for unlimited.
        @type maxSize: C{int}
        """
        self._cache = {}
        self._cacheSize = 0
        self.maxSize = maxSize
        self._order = []


    def setMaxSize(self, maxSize):
        """
        """
        self.maxSize = maxSize
        if self._cacheSize > self.maxSize:
            self._clearCache(maxSize/4)


    def get(self, key):
        """
        Retrieve the value associated from the key in the cache.

        @raise KeyNotFoundError: if the given key is not in the cache.

        @return: a L{Deferred} firing with the tuple (flags, value)
        @rtype: L{Deferred}
        """
        cachedValue = self._cache.get(key)
        if cachedValue is None:
            return fail(KeyNotFoundError(key))
        return succeed((cachedValue.flags, cachedValue.value))


    def gets(self, key):
        """
        @raise KeyNotFoundError: if the given key is not in the cache.

        @return: a L{Deferred} firing with the tuple (flags, cas identifier,
            value)
        @rtype: L{Deferred}
        """
        cachedValue = self._cache.get(key)
        if cachedValue is None:
            return fail(KeyNotFoundError(key))
        return succeed(
            (cachedValue.flags, cachedValue.casValue, cachedValue.value))


    def _clearCache(self, howMany=0):
        """
        Empty the cache.
        """
        while self._cacheSize > self.maxSize - howMany:
            key = self._order.pop(0)
            value = self._cache.pop(key)
            self._cacheSize -= value.value


    def _set(self, key, value, flags, expireTime):
        """
        Helper method for set operations.
        """
        if self.maxSize and self._cacheSize + len(value) > self.maxSize:
            # We have to drop keys
            self._clearCache(self._cacheSize/4)
        self._cacheSize += len(value)
        value = _CachedValue(value, flags, expireTime)
        self._cache[key] = value
        if not 'key' in self._order:
            self._order.append(key)
        return succeed(True)


    def set(self, key, value, flags, expireTime):
        """
        Set the content associated with C{key} to C{value}.

        @param key:
        @type key: C{str}

        @param value:
        @type value: C{str}

        @param flags:
        @type flags:

        @param expireTime:
        @type expireTime:

        @return: a L{Deferred} that will fire with C{True} if the operation has
            succeeded.
        @rtype: L{Deferred}
        """
        return self._set(key, value, flags, expireTime)


    def checkAndSet(self, key, value, flags, expireTime, casValue):
        """
        Set the content associated with C{key} to C{value} only if the given
        C{casValue} match the current one associated with the key.

        @return: a L{Deferred} that will fire with C{True} if the operation has
            succeeded.
        @rtype: L{Deferred}
        """
        if not key in self._cache:
            return fail(KeyNotFoundError(key))
        if self._cache[key].casValue != casValue:
            return fail(CasError(key, casValue))
        return self._set(key, value, flags, expireTime)


    def add(self, key, value, flags, expireTime):
        """
        Set the content for the given C{key} to C{value} only if the key is not
        yet in the cache.
        """
        if key in self._cache:
            return fail(KeyFoundError(key))
        return self._set(key, value, flags, expireTime)


    def replace(self, key, value, flags, expireTime):
        """
        Set the content for the given C{key} to C{value} only if the key is
        already in the cache.
        """
        if not key in self._cache:
            return fail(KeyNotFoundError(key))
        return self._set(key, value, flags, expireTime)


    def append(self, key, value, flags, expireTime):
        """
        Append the given C{value} to the current value associated with the
        C{key}. The key has to be in the cache.
        """
        if not key in self._cache:
            return fail(KeyNotFoundError(key))
        currentValue = self._cache[key]
        currentValue.value += value
        return succeed(True)


    def prepend(self, key, value, flags, expireTime):
        """
        Prepend the given C{value} to the current value associated with the
        C{key}. The key has to be in the cache.
        """
        if not key in self._cache:
            return fail(KeyNotFoundError(key))
        currentValue = self._cache[key]
        currentValue.value = value + currentValue.value
        return succeed(True)


    def delete(self, key):
        """
        Delete the given C{key} from the cache. The key has to be in the cache.
        """
        if key not in self._cache:
            return fail(KeyNotFoundError(key))
        del self._cache[key]
        self._order.remove(key)
        return succeed(True)


    def increment(self, key, value):
        """
        Increment the value associated with the key with C{value}. The current
        value and the given value should be coercible to an integer.
        """
        if key not in self._cache:
            return fail(KeyNotFoundError(key))
        try:
            self._cache[key].value = str(
                int(self._cache[key].value) + int(value))
        except ValueError:
            return fail()
        return succeed(self._cache[key].value)


    def decrement(self, key, value):
        """
        Decrement the value associated with the key with C{value}. The current
        value and the given value should be coercible to an integer.
        """
        if key not in self._cache:
            return fail(KeyNotFoundError(key))
        try:
            self._cache[key].value = str(
                int(self._cache[key].value) - int(value))
        except ValueError:
            return fail()
        return succeed(self._cache[key].value)


    def flush_all(self):
        """
        Empty the cache.

        @return: a L{Deferred} firing with C{True}.
        @rtype: L{Deferred}
        """
        self._cache = {}
        return succeed(True)


    def stats(self):
        """
        Return some statistics of the current status of the cache.
        """
        stats = {"curr_items": len(self._cache)}
        return succeed(stats)


    def version(self):
        """
        Return the version of the backend.
        """
        return succeed("1.0")



class _ServerCommand(object):
    """
    Represent a current pending commad server-side.
    """

    def __init__(self, command, **kwargs):
        """
        Create a command.

        @param command: the name of the command.
        @type command: C{str}

        @param kwargs: values stored as attributes of the object for future
            use.
        """
        self.command = command
        self.isReady = False
        self.value = ""
        for k, v in kwargs.items():
            setattr(self, k, v)



class MemCacheServerProtocol(LineReceiver, TimeoutMixin):
    """
    Implementation of memcache server protocol.

    @ivar backend: backend managing the cache.
    @type backend: a provider of L{ICacheBackend}
    """
    backendFactory = StandardBackend

    def __init__(self):
        """
        Initialize the protocol and the internal structures.
        """
        self.backend = self.backendFactory()
        self._current = deque()
        self._lenExpected = None
        self._getBuffer = None
        self._bufferLength = None


    def timeoutConnection(self):
        """
        On timeout, clear current commands and close transport.
        """
        self._current = deque()
        self.transport.loseConnection()


    def rawDataReceived(self, data):
        """
        Manage data received during set operations.
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
            cmd.value = val
            self.setLineMode(rem)
            method = getattr(self.backend, cmd.command)
            if cmd.command == "cas":
                d = method(cmd.key, cmd.value, cmd.flags, cmd.expireTime,
                           cmd.casValue)
            else:
                d = method(cmd.key, cmd.value, cmd.flags, cmd.expireTime)
            d.addCallback(self._responseSet, cmd)


    def _popResponses(self, cmd):
        """
        Fire up response, if given command is the first in the queue.
        """
        cmd.isReady = True
        if not cmd is self._current[0]:
            return
        while self._current and self._current[0].isReady:
            self.sendLine(self._current[0].value)
            self._current.popleft()


    def _responseSet(self, result, cmd):
        """
        Reply to a set query with the C{STORED} token.
        """
        if result:
            cmd.value = "STORED"

        self._popResponses(cmd)


    def _responseGet(self, data, cmd):
        """
        Reply to the get query with the value got from the the store.
        """
        value = "VALUE %s %s %s\r\n%s\r\nEND" % (
            cmd.key, data[0], len(data[1]), data[1])
        cmd.value = value

        self._popResponses(cmd)


    def _errorGet(self, err, cmd):
        """
        """
        err.trap(KeyNotFoundError)
        cmd.value = "END"
        self._popResponses(cmd)


    def _responseGets(self, data, cmd):
        """
        Reply to the get query with the value got from the the store, along
        with the cas value.
        """
        value = "VALUE %s %s %s %s\r\n%s\r\nEND" % (
            cmd.key, data[0], len(data[2]), data[1], data[2])
        cmd.value = value

        self._popResponses(cmd)


    def cmd_GET(self, key):
        """
        Manage C{get} command.
        """
        cmd = _ServerCommand("get", key=key)
        self._current.append(cmd)
        d = self.backend.get(key)
        d.addCallback(self._responseGet, cmd)
        d.addErrback(self._errorGet, cmd)
        return d


    def cmd_GETS(self, key):
        """
        Manage C{gets} command.
        """
        cmd = _ServerCommand("gets", key=key)
        self._current.append(cmd)
        d = self.backend.gets(key)
        d.addCallback(self._responseGets, cmd)
        d.addErrback(self._errorGet, cmd)
        return d


    def _prepareSet(self, cmd, key, flags, expireTime, length, casValue=""):
        """
        Common code to all set operations.
        """
        cmd = _ServerCommand(cmd, key=key, flags=int(flags),
            expireTime=int(expireTime), length=int(length), casValue=casValue)
        self._current.append(cmd)
        self._lenExpected = int(length)
        self._getBuffer = []
        self._bufferLength = 0
        self.setRawMode()


    def cmd_SET(self, key, flags, expireTime, length):
        """
        Reply to the C{set} command.
        """
        self._prepareSet("set", key, flags, expireTime, length)


    def cmd_ADD(self, key, flags, expireTime, length):
        """
        Reply to the C{add} command.
        """
        self._prepareSet("add", key, flags, expireTime, length)


    def cmd_REPLACE(self, key, flags, expireTime, length):
        """
        Reply to the C{replace} command.
        """
        self._prepareSet("replace", key, flags, expireTime, length)


    def cmd_APPEND(self, key, flags, expireTime, length):
        """
        Reply to the C{append} command.
        """
        self._prepareSet("append", key, flags, expireTime, length)


    def cmd_PREPEND(self, key, flags, expireTime, length):
        """
        Reply to the C{prepend} command.
        """
        self._prepareSet("prepend", key, flags, expireTime, length)


    def cmd_CAS(self, key, flags, expireTime, length, casValue):
        """
        Reply to the C{cas} command.
        """
        self._prepareSet(
            "checkAndSet", key, flags, expireTime, length, casValue)


    def _responseDelete(self, result, cmd):
        """
        Serialize response to the C{delete} command.
        """
        cmd.value = "DELETED"

        self._popResponses(cmd)


    def cmd_DELETE(self, key):
        """
        Manage C{delete} command.
        """
        cmd = _ServerCommand("delete", key=key)
        self._current.append(cmd)
        return self.backend.delete(key).addCallback(self._responseDelete, cmd)


    def _responseIncrDecr(self, result, cmd):
        """
        Serialize response to C{incr} and C{decr} commands.
        """
        cmd.value = result

        self._popResponses(cmd)


    def _errorIncrDecr(self, result, cmd):
        """
        """
        if result.check(KeyNotFoundError) is not None:
            cmd.value = "NOT FOUND"
        else:
            cmd.value = "CLIENT_ERROR %s" % (str(result.value),)

        self._popResponses(cmd)


    def cmd_INCR(self, key, value):
        """
        Manage C{incr} command.
        """
        cmd = _ServerCommand("increment", key=key)
        self._current.append(cmd)
        return self.backend.increment(key, value
            ).addCallback(self._responseIncrDecr, cmd
            ).addErrback(self._errorIncrDecr, cmd)


    def cmd_DECR(self, key, value):
        """
        Manage C{decr} command.
        """
        cmd = _ServerCommand("decrement", key=key)
        self._current.append(cmd)
        return self.backend.decrement(key, value
            ).addCallback(self._responseIncrDecr, cmd
            ).addErrback(self._errorIncrDecr, cmd)


    def _responseStats(self, result, cmd):
        """
        Manage response to the stats command.
        """
        cmd.value = ""
        for key, value in result.iteritems():
            cmd.value += "STAT %s %s\r\n" % (key, value)
        cmd.value += "END"

        self._popResponses(cmd)


    def cmd_STATS(self):
        """
        Manage C{stats} command.
        """
        cmd = _ServerCommand("stats")
        self._current.append(cmd)
        return self.backend.stats().addCallback(self._responseStats, cmd)


    def _responseVersion(self, result, cmd):
        """
        Manage response to the version command.
        """
        cmd.value = "VERSION %s" % (result,)

        self._popResponses(cmd)


    def cmd_VERSION(self):
        """
        Manage C{version} command.
        """
        cmd = _ServerCommand("version")
        self._current.append(cmd)
        return self.backend.version().addCallback(self._responseVersion, cmd)


    def _responseFlush(self, result, cmd):
        """
        Manage response to the flush command.
        """
        cmd.value = "OK"

        self._popResponses(cmd)


    def cmd_FLUSH_ALL(self):
        """
        Manage C{flush} command.
        """
        cmd = _ServerCommand("flush_all")
        self._current.append(cmd)
        return self.backend.flush_all().addCallback(self._responseFlush, cmd)


    def lineReceived(self, line):
        """
        Receive line commands from the client.
        """
        self.resetTimeout()
        token = line.split(" ", 1)[0]
        cmd = getattr(self, "cmd_%s" % (token.upper(),), None)
        if cmd is not None:
            args = line.split(" ")[1:]
            cmd(*args)
        else:
            raise RuntimeError("Unknown command %s" % (token,))


__all__ = ["MemCacheProtocol", "DEFAULT_PORT", "NoSuchCommand", "ClientError",
           "ServerError", "MemCacheServerProtocol", "ICacheBackend",
           "StandardBackend", "KeyFoundError", "KeyNotFoundError", "CasError"]

