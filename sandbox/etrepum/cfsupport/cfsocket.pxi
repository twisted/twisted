cdef class PyCFSocket

cdef void socketCallBack(CFSocketRef s, CFSocketCallBackType _type, CFDataRef address, void *data, void *info):
    cdef PyCFSocket socket
    cdef int res
    socket = (<PyCFSocket>info)
    #print "fileno = %r" % (socket.fileno,)
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

cdef class PyCFSocket:
    cdef public object readcallback
    cdef public object writecallback
    cdef public object connectcallback
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
        self.cf = CFSocketCreateWithNative(kCFAllocatorDefault, fileno, kCFSocketReadCallBack|kCFSocketWriteCallBack|kCFSocketConnectCallBack, <CFSocketCallBack>&socketCallBack, &self.context)
        if self.cf == NULL:
            raise ValueError("Invalid Socket")
        CFSocketSetSocketFlags(self.cf, kCFSocketAutomaticallyReenableReadCallBack|kCFSocketAutomaticallyReenableWriteCallBack)

        self.source = CFSocketCreateRunLoopSource(kCFAllocatorDefault, self.cf, 10000)
        if self.source == NULL:
            raise ValueError("Couldn't create runloop source")
        #print "made new socket"
        
    def startReading(self):
        CFSocketEnableCallBacks(self.cf, kCFSocketReadCallBack)

    def stopReading(self):
        CFSocketDisableCallBacks(self.cf, kCFSocketReadCallBack)
        
    def startWriting(self):
        CFSocketEnableCallBacks(self.cf, kCFSocketWriteCallBack)

    def stopWriting(self):
        CFSocketDisableCallBacks(self.cf, kCFSocketWriteCallBack)

    def __dealloc__(self):
        #print "PyCFSocket(%r).__dealloc__()" % (self.fileno,)
        if self.source != NULL:
            CFRelease(self.source)
        if self.cf != NULL:
            CFSocketInvalidate(self.cf)
            CFRelease(self.cf)
        #print "__dealloc__()"
