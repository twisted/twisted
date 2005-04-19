import traceback
import warnings
import types


cdef extern from "Python.h":
    cdef void Py_INCREF(object op)
    cdef int PyList_GET_SIZE(object op) except -1
    cdef object PyList_GET_ITEM(object op, int i)
    cdef object PyTuple_GET_ITEM(object op, int i)
    cdef int PyList_SetItem(object op, int i, object newitem) except -1
    cdef int PyList_Append(object op, object newitem) except -1
    cdef int PyList_SetSlice(object op, int ilow, int ihigh, void *v) except -1
    cdef int isinstance  "PyObject_IsInstance"(object op1, object op2)
    cdef int PyObject_TypeCheck(object op1, object op2)
    cdef int callable "PyCallable_Check"(object op)
    cdef void PyObject_GC_UnTrack(op)

cdef extern from "hack.h":
    cdef object Pyrex_GETTYPE(ob)

# Twisted imports
from twisted.python import log, failure
from twisted.python.failure import Failure
from twisted.python.util import unsignedID
from twisted.internet.defer import AlreadyCalledError, timeout, DebugInfo

# Marker for lack of result
cdef object _marker
_marker = object()

cdef object PyClass_Type
PyClass_Type = types.ClassType

# enable .debug to record creation/first-invoker call stacks, and they
# will be added to any AlreadyCalledErrors we raise
def setDebugging(new_debug):
    global debug
    if new_debug:
        debug=1
    else:
        debug=0

cdef int debug

cdef class Deferred:
    """This is a callback which will be put off until later.

    Why do we want this? Well, in cases where a function in a threaded
    program would block until it gets a result, for Twisted it should
    not block. Instead, it should return a Deferred.

    This can be implemented for protocols that run over the network by
    writing an asynchronous protocol for twisted.internet. For methods
    that come from outside packages that are not under our control, we use
    threads (see for example L{twisted.enterprise.adbapi}).

    For more information about Deferreds, see doc/howto/defer.html or
    U{http://www.twistedmatrix.com/documents/howto/defer}
    """
    property called:
        def __get__(self):
            return self.result is not _marker

    cdef public object result
    cdef readonly int paused
    cdef readonly object callbacks
    cdef readonly int isFailure
    cdef readonly object debugInfo
    
    def __init__(self):
        self.paused = 0
        self.callbacks = []
        self.result = _marker
        self.isFailure = 0
        if debug:
            self.debugInfo = DebugInfo()
            self.debugInfo.creator = traceback.format_stack()[:-1]
        
    cdef _addCallbacks(self, callback, errback,
                     callbackArgs, callbackKeywords,
                     errbackArgs, errbackKeywords):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        assert callback is None or callable(callback)
        assert errback is None or callable(errback)
        PyList_Append(self.callbacks,
            (callback, callbackArgs, callbackKeywords,
               errback, errbackArgs, errbackKeywords))
        if self.result is not _marker:
            self._runCallbacks()
        return self

    def addCallbacks(self, callback, errback=None,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        return self._addCallbacks(callback, errback,
                                  callbackArgs, callbackKeywords,
                                  errbackArgs, errbackKeywords)
    
    def addCallback(self, callback, *args, **kw):
        """Convenience method for adding just a callback.

        See L{addCallbacks}.
        """
        if not args: args = None
        if not kw: kw = None
        return self._addCallbacks(callback, None, args, kw, None, None)

    def addErrback(self, errback, *args, **kw):
        """Convenience method for adding just an errback.

        See L{addCallbacks}.
        """
        if not args: args = None
        if not kw: kw = None
        return self._addCallbacks(None, errback, None, None, args, kw)

    def addBoth(self, callback, *args, **kw):
        """Convenience method for adding a single callable as both a callback
        and an errback.

        See L{addCallbacks}.
        """
        if not args: args = None
        if not kw: kw = None
        return self._addCallbacks(callback, callback, args, kw, args, kw)

    def chainDeferred(self, d):
        """Chain another Deferred to this Deferred.

        This method adds callbacks to this Deferred to call d's callback or
        errback, as appropriate."""
        return self._addCallbacks(d.callback, d.errback, None, None, None, None)

    def callback(self, result):
        """Run all success callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'. Also, if the success-callback returns a Failure
        or raises an Exception, processing will continue on the *error*-
        callback chain.
        """
        assert not PyObject_TypeCheck(result, Deferred)
        self._startRunCallbacks(result)


    def errback(self, fail=None):
        """Run all error callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'. Also, if the error-callback returns a non-Failure
        or doesn't raise an Exception, processing will continue on the
        *success*-callback chain.

        If the argument that's passed to me is not a Failure instance,
        it will be embedded in one. If no argument is passed, a Failure
        instance will be created based on the current traceback stack.

        Passing a string as `fail' is deprecated, and will be punished with
        a warning message.
        """
        if not (Pyrex_GETTYPE(fail) is PyClass_Type and fail.__class__ is Failure):
            fail = Failure(fail)

        self._startRunCallbacks(fail)


    def pause(self):
        """Stop processing on a Deferred until L{unpause}() is called.
        """
        self.paused = self.paused + 1


    def unpause(self):
        """Process all callbacks made since L{pause}() was called.
        """
        self.paused = self.paused - 1
        if self.paused:
            return
        if self.result is not _marker:
            self._runCallbacks()

    def _continue(self, result):
        self.result = result
        self.unpause()

    cdef _startRunCallbacks(self, result):
        if self.result is not _marker:
            if self.debugInfo is not None:
                extra = "\n" + self.debugInfo._debugInfo()
                raise AlreadyCalledError(extra)
            raise AlreadyCalledError
        
        if self.debugInfo is not None:
            self.debugInfo.invoker = traceback.format_stack()[:-2]

        self.result = result
        self._runCallbacks()

    cdef _runCallbacks(self):
        cdef int i, size, offset
        offset = 0
        
        if not self.paused:
            cb = self.callbacks
            size = PyList_GET_SIZE(cb)
            for i from 0 <= i < size:
                item = PyList_GET_ITEM(cb, i)
                Py_INCREF(item)
                if (Pyrex_GETTYPE(self.result) is PyClass_Type and self.result.__class__ is Failure):
                    offset = 3
                callback = PyTuple_GET_ITEM(item, offset+0)
                Py_INCREF(callback)
                args = PyTuple_GET_ITEM(item, offset+1)
                Py_INCREF(args)
                kw = PyTuple_GET_ITEM(item, offset+2)
                Py_INCREF(kw)
                
                if callback is not None:
                    try:
                        # Doing this mess of ifs is necessary because */** doesn't 
                        # work with None. Also it's faster this way than using (),{}.
                        if kw is None:
                            if args is None:
                                self.result = callback(self.result)
                            else:
                                self.result = callback(self.result, *args)
                        else:
                            if args is None:
                                self.result = callback(self.result, **kw)
                            else:
                                self.result = callback(self.result, *args, **kw)

                        if PyObject_TypeCheck(self.result, Deferred):
                            PyList_SetSlice(cb, 0, i+1, NULL)

                            # note: this will cause _runCallbacks to be called
                            # "recursively" sometimes... this shouldn't cause any
                            # problems, since all the state has been set back to
                            # the way it's supposed to be, but it is useful to know
                            # in case something goes wrong.  deferreds really ought
                            # not to return themselves from their callbacks.
                            self.pause()
                            self.result.addBoth(self._continue)
                            break
                    except:
                        self.result = Failure()
            else:
                PyList_SetSlice(cb, 0, PyList_GET_SIZE(cb), NULL)
        
        if (Pyrex_GETTYPE(self.result) is PyClass_Type and self.result.__class__ is Failure):
            if self.debugInfo is None:
                self.isFailure = 1
            else:
                self.debugInfo.failResult = self.result
            self.result.cleanFailure()
        else:
            if self.debugInfo is None:
                self.isFailure = 0
            else:
                self.debugInfo.failResult = None

    def __str__(self):
        cname = self.__class__.__name__
        if self.called:
            return "<%s at %s  current result: %r>" % (cname, hex(unsignedID(self)),
                                                       self.result)
        return "<%s at %s>" % (cname, hex(unsignedID(self)))
    def __repr__(self):
        return self.__str__()

    def __dealloc__(self):
        # Ugh, work around pyrex bug! It should be calling untrack for me!
        PyObject_GC_UnTrack(self)
        
        # Be very careful to not do anything posibly memory-corruptful.
        # Python objects we reference may not be valid anymore.
        if self.isFailure:
            log.msg("Unhandled error in Deferred (no debugging info available)", isError=1)


    def _timeout(self, timeoutFunc, args, kw):
        if not self.called:
            timeoutFunc(self, *args, **kw)
    
    def setTimeout(self, seconds, timeoutFunc=timeout, *args, **kw):
        """Set a timeout function to be triggered if I am not called.

        @param seconds: How long to wait (from now) before firing the
        timeoutFunc.

        @param timeoutFunc: will receive the Deferred and *args, **kw as its
        arguments.  The default timeoutFunc will call the errback with a
        L{TimeoutError}.

        DON'T USE THIS! It's a bad idea! Use a function called by reactor.callLater instead
        to accomplish the same thing!

        YOU HAVE BEEN WARNED!
        """

        warnings.warn("Deferred.setTimeout is deprecated. It's a bad idea, don't use it.",
                      DeprecationWarning, stacklevel=2)
        if self.called:
            return

        from twisted.internet import reactor
        return reactor.callLater(seconds, self._timeout, timeoutFunc, args, kw)

