import traceback

cdef class PyCFSocket

cdef void socketCallBack(CFSocketRef s, CFSocketCallBackType _type, CFDataRef address, void *data, void *info):
    cdef PyCFSocket socket
    cdef int res
    cdef int mask
    socket = (<PyCFSocket>info)
    #print "fileno = %r" % (socket.fileno,)
    try:
        if _type == kCFSocketReadCallBack:
            if socket.readcallback:
                socket.readcallback()
        elif _type == kCFSocketWriteCallBack:
            if socket.writecallback:
                socket.writecallback()
        elif _type == kCFSocketConnectCallBack:
            if data == NULL:
                res = 0
            else:
                res = (<int*>data)[0]
            if socket.connectcallback:
                socket.connectcallback(res)
    except:
        traceback.print_exc()
    
cdef void gilSocketCallBack(CFSocketRef s, CFSocketCallBackType _type, CFDataRef address, void *data, void *info):
    cdef PyGILState_STATE gil
    gil = PyGILState_Ensure()
    socketCallBack(s, _type, address, data, info)
    PyGILState_Release(gil)

cdef class PyCFSocket:
    cdef public object readcallback
    cdef public object writecallback
    cdef public object connectcallback
    cdef public object reading
    cdef public object writing
    cdef CFSocketRef cf
    cdef CFRunLoopSourceRef source
    cdef readonly CFSocketNativeHandle fileno
    cdef CFSocketContext context

    def __new__(self, CFSocketNativeHandle fileno, readcallback=None, writecallback=None, connectcallback=None):
        #print "new socket %r" % (fileno,)
        self.fileno = fileno
        self.readcallback = readcallback
        self.writecallback = writecallback
        self.connectcallback = connectcallback
        self.context.version = 0
        self.context.info = <void *>self
        self.context.retain = NULL
        self.context.release = NULL
        self.context.copyDescription = NULL
        self.reading = False
        self.writing = False
        self.cf = CFSocketCreateWithNative(kCFAllocatorDefault, fileno, kCFSocketConnectCallBack | kCFSocketReadCallBack | kCFSocketWriteCallBack, <CFSocketCallBack>&gilSocketCallBack, &self.context)
        if self.cf == NULL:
            raise ValueError("Invalid Socket")
        self.source = CFSocketCreateRunLoopSource(kCFAllocatorDefault, self.cf, 10000)
        if self.source == NULL:
            raise ValueError("Couldn't create runloop source")
        #print "made new socket"
        
    def update(self):
        cdef int mask
        cdef int offmask
        cdef int automask
        mask = kCFSocketConnectCallBack | kCFSocketAcceptCallBack
        offmask = 0
        automask = kCFSocketAutomaticallyReenableAcceptCallBack
        if self.reading:
            mask = mask | kCFSocketReadCallBack
            automask = automask | kCFSocketAutomaticallyReenableReadCallBack
        else:
            offmask = offmask | kCFSocketReadCallBack
        if self.writing:
            mask = mask | kCFSocketWriteCallBack
            automask = automask | kCFSocketAutomaticallyReenableWriteCallBack
        else:
            offmask = offmask | kCFSocketWriteCallBack
        CFSocketDisableCallBacks(self.cf, offmask)
        CFSocketEnableCallBacks(self.cf, mask)
        CFSocketSetSocketFlags(self.cf, automask)
        
    
    def startReading(self):
        self.reading = True
        self.update()

    def stopReading(self):
        self.reading = False
        self.update()
        
    def startWriting(self):
        self.writing = True
        self.update()

    def stopWriting(self):
        self.writing = False
        self.update()

    def __dealloc__(self):
        #print "PyCFSocket(%r).__dealloc__()" % (self.fileno,)
        if self.source != NULL:
            CFRelease(self.source)
        if self.cf != NULL:
            CFSocketInvalidate(self.cf)
            CFRelease(self.cf)
        #print "__dealloc__()"
