import traceback

# possibly figure out how to subclass these or something

cdef class PyCFRunLoopTimer:
    cdef CFRunLoopTimerRef cf
    cdef public object callout
    cdef CFRunLoopTimerContext context

    def __new__(self, double fireDate, double interval, callout):
        self.callout = callout
        self.context.version = 0
        self.context.info = <void *>self
        self.context.retain = NULL
        self.context.release = NULL
        self.context.copyDescription = NULL
        self.cf = CFRunLoopTimerCreate(kCFAllocatorDefault, fireDate, interval, 0, 0, <CFRunLoopTimerCallBack>&gilRunLoopTimerCallBack, &self.context)
        if self.cf == NULL:
            raise ValueError("Invalid Socket")
        
    def getNextFireDate(self):
        return CFRunLoopTimerGetNextFireDate(self.cf)

    def setNextFireDate(self, double fireDate):
        CFRunLoopTimerSetNextFireDate(self.cf, fireDate)

    def invalidate(self):
        CFRunLoopTimerInvalidate(self.cf)

    def __dealloc__(self):
        if self.cf != NULL:
            CFRelease(self.cf)

cdef void runLoopTimerCallBack(CFRunLoopTimerRef timer, void *info):
    cdef PyCFRunLoopTimer obj
    obj = <PyCFRunLoopTimer>info
    try:
        if obj.callout:
            obj.callout()
    except:
        traceback.print_exc()

cdef void gilRunLoopTimerCallBack(CFRunLoopTimerRef timer, void *info):
    cdef PyGILState_STATE gil
    gil = PyGILState_Ensure()
    runLoopTimerCallBack(timer, info)
    PyGILState_Release(gil)

cdef class PyCFRunLoop:
    cdef public object cf

    def __new__(self, runLoop=None):
        cdef CFTypeRef _runLoop
        if runLoop is None:
            _runLoop = CFRunLoopGetCurrent()
        else:
            if CFObj_Convert(runLoop, &_runLoop) == 0:
                raise
                #return -1
        # this is going to leak a reference
        self.cf = CFObj_New(CFRetain(_runLoop))

    def run(self):
        CFRunLoopRun()

    def stop(self):
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        CFRunLoopStop(_runLoop)

    def currentMode(self):
        cdef CFTypeRef _currentMode
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        _currentMode = CFRunLoopCopyCurrentMode(_runLoop)
        if _currentMode == NULL:
            return None
        return CFObj_New(_currentMode)
        
    def addSocket(self, PyCFSocket socket not None):
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        CFRunLoopAddSource(_runLoop, socket.source, kCFRunLoopCommonModes)

    def removeSocket(self, PyCFSocket socket not None):
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        CFRunLoopRemoveSource(_runLoop, socket.source, kCFRunLoopCommonModes)

    def addTimer(self, PyCFRunLoopTimer timer not None):
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        CFRunLoopAddTimer(_runLoop, timer.cf, kCFRunLoopCommonModes)

    def removeTimer(self, PyCFRunLoopTimer timer not None):
        cdef CFTypeRef _runLoop
        if CFObj_Convert(self.cf, &_runLoop) == 0:
            raise ValueError, "CFRunLoopReference is invalid"
        CFRunLoopRemoveTimer(_runLoop, timer.cf, kCFRunLoopCommonModes)
