cdef extern from "pymactoolbox.h":
    # CFBase
    ctypedef void *CFTypeRef
    ctypedef CFTypeRef CFAllocatorRef
    ctypedef CFTypeRef CFStringRef
    ctypedef CFStringRef CFMutableStringRef
    ctypedef CFTypeRef CFDataRef
    ctypedef CFDataRef CFMutableDataRef
    ctypedef CFTypeRef CFArrayRef
    ctypedef CFArrayRef CFMutableArrayRef
    ctypedef CFTypeRef CFDictionaryRef
    ctypedef CFDictionaryRef CFMutableDictionaryRef
    ctypedef CFTypeRef CFURLRef 

    ctypedef unsigned short UniChar
    ctypedef int CFIndex
    ctypedef int CFOptionFlags
    ctypedef int Boolean

    ctypedef struct CFRange:
        CFIndex location
        CFIndex length

    cdef extern CFAllocatorRef kCFAllocatorDefault
    cdef extern CFAllocatorRef kCFAllocatorNull

    cdef CFTypeRef CFRetain(CFTypeRef cf)
    cdef void CFRelease(CFTypeRef cf)
    cdef CFIndex CFGetRetainCount(CFTypeRef cf)
    cdef CFStringRef CFCopyDescription(CFTypeRef cf)
    cdef CFRange CFRangeMake(CFIndex location, CFIndex length)

    # CFData
    cdef CFDataRef CFDataCreate(CFAllocatorRef allocator, unsigned char *bytes, CFIndex length)
    cdef CFDataRef CFDataCreateWithBytesNoCopy(CFAllocatorRef, unsigned char *bytes, CFIndexLength, CFAllocatorRef bytesDeallocator)
    cdef CFMutableDataRef CFDataCreateMutable(CFAllocatorRef allocator, CFIndex capacity)
    cdef CFMutableDataRef CFDataCreateMutableCopy(CFAllocatorRef allocator, CFIndex capacity, CFDataRef theData)
    cdef CFIndex CFDataGetLength(CFDataRef theData)
    cdef unsigned char *CFDataGetBytePtr(CFDataRef theData)
    cdef unsigned char *CFDataGetMutableBytePtr(CFMutableDataRef theData)
    cdef CFDataGetBytes(CFDataRef theData, CFRange range, unsigned char *buffer)
    cdef CFDataSetLength(CFMutableDataRef theData, CFIndex length)
    cdef CFDataIncreaseLength(CFMutableDataRef theData, CFIndex extraLength)
    cdef CFDataAppendBytes(CFMutableDataRef theData, unsigned char *bytes, CFIndex length)
    cdef CFDataReplaceBytes(CFMutableDataRef theData, CFRange range, unsigned char *newBytes, CFIndex newLength)
    cdef CFDataDeleteBytes(CFMutableDataRef theData, CFRange range)
    
    
    # CFString

    ctypedef enum CFStringBuiltInEncodings:
        kCFStringEncodingMacRoman = 0
        kCFStringEncodingWindowsLatin1 = 0x0500
        kCFStringEncodingISOLatin1 = 0x0201
        kCFStringEncodingNextStepLatin = 0x0B01
        kCFStringEncodingASCII = 0x0600
        kCFStringEncodingUnicode = 0x0100
        kCFStringEncodingUTF8 = 0x08000100
        kCFStringEncodingNonLossyASCII = 0x0BFF
        kCFStringEncodingInvalidId = 0xffffffff
    ctypedef unsigned int CFStringEncoding

    cdef void CFStringGetCharacters(CFStringRef theString, CFRange range, UniChar *ubuffer)
    cdef CFIndex CFStringGetLength(CFStringRef theString)
    cdef CFStringRef CFStringCreateWithCString(CFAllocatorRef alloc, char *cStr, CFStringEncoding encoding)
    cdef CFStringRef CFStringCreateWithCharacters(CFAllocatorRef alloc, UniChar *chars, CFIndex numChars)
    
    # CFArray

    cdef CFIndex CFArrayGetCount(CFArrayRef theArray)
    cdef void *CFArrayGetValueAtIndex(CFArrayRef theArray, CFIndex idx)
    cdef void CFArrayGetValues(CFArrayRef theArray, CFRange range, void **values)
    
    # CFDate
    ctypedef double CFTimeInterval
    ctypedef CFTimeInterval CFAbsoluteTime

    cdef CFAbsoluteTime CFAbsoluteTimeGetCurrent()

    # CFRunLoop
    ctypedef struct CFRunLoopTimerContext:
        CFIndex version
        void* info
        void *(*retain)(void *info)
        void (*release)(void *info)
        CFStringRef (*copyDescription)(void *info)

    ctypedef CFTypeRef CFRunLoopRef
    ctypedef CFTypeRef CFRunLoopTimerRef
    ctypedef CFTypeRef CFRunLoopSourceRef
    ctypedef void (*CFRunLoopTimerCallBack)(CFRunLoopTimerRef timer, void *info)

    cdef extern CFStringRef kCFRunLoopCommonModes

    cdef CFRunLoopRef CFRunLoopGetCurrent()
    cdef void CFRunLoopRun()
    cdef void CFRunLoopStop(CFRunLoopRef rl)
    cdef void CFRunLoopAddSource(CFRunLoopRef rl, CFRunLoopSourceRef source, CFStringRef mode)
    cdef void CFRunLoopRemoveSource(CFRunLoopRef rl, CFRunLoopSourceRef source, CFStringRef mode)
    cdef CFStringRef CFRunLoopCopyCurrentMode(CFRunLoopRef rl)

    cdef void CFRunLoopAddTimer(CFRunLoopRef rl, CFRunLoopTimerRef timer, CFStringRef mode)
    cdef void CFRunLoopRemoveTimer(CFRunLoopRef rl, CFRunLoopTimerRef timer, CFStringRef mode)

    cdef CFRunLoopTimerRef CFRunLoopTimerCreate(CFAllocatorRef allocator, CFAbsoluteTime fireDate, CFTimeInterval interval, CFOptionFlags flags, CFIndex order, CFRunLoopTimerCallBack callout, CFRunLoopTimerContext *context)
    cdef CFAbsoluteTime CFRunLoopTimerGetNextFireDate(CFRunLoopTimerRef timer)
    cdef void CFRunLoopTimerSetNextFireDate(CFRunLoopTimerRef timer, CFAbsoluteTime fireDate)
    cdef void CFRunLoopTimerInvalidate(CFRunLoopTimerRef timer)
    
    # CFSocket 
    enum kCFSocketFlags:
        kCFSocketAutomaticallyReenableReadCallBack = 1
        kCFSocketAutomaticallyReenableAcceptCallBack = 2
        kCFSocketAutomaticallyReenableDataCallBack = 3
        kCFSocketAutomaticallyReenableWriteCallBack = 8
        kCFSocketCloseOnInvalidate = 128

    ctypedef enum CFSocketCallBackType:
        kCFSocketNoCallBack = 0
        kCFSocketReadCallBack = 1
        kCFSocketAcceptCallBack = 2
        kCFSocketDataCallBack = 3
        kCFSocketConnectCallBack = 4
        kCFSocketWriteCallBack = 8

    ctypedef struct CFSocketContext:
        CFIndex version
        void *info
        void *(*retain)(void *info)
        void (*release)(void *info)
        CFStringRef (*copyDescription)(void *info)

    ctypedef int CFSocketNativeHandle
    ctypedef void *CFSocketRef
    ctypedef void (*CFSocketCallBack)(CFSocketRef s, CFSocketCallBackType _type, CFDataRef address, void *data, void *info)

    cdef CFSocketRef CFSocketCreateWithNative(CFAllocatorRef allocator, CFSocketNativeHandle sock, CFOptionFlags callbackTypes, CFSocketCallBack callout, CFSocketContext* context)
    cdef CFSocketNativeHandle CFSocketGetNative(CFSocketRef s)
    cdef CFRunLoopSourceRef CFSocketCreateRunLoopSource(CFAllocatorRef allocator, CFSocketRef s, CFIndex order)
    cdef void CFSocketEnableCallBacks(CFSocketRef s, CFOptionFlags callBackTypes)
    cdef void CFSocketDisableCallBacks(CFSocketRef s, CFOptionFlags callBackTypes)
    cdef CFOptionFlags CFSocketGetSocketFlags(CFSocketRef s)
    cdef void CFSocketSetSocketFlags(CFSocketRef s, CFOptionFlags socketFlags)
    cdef void CFSocketInvalidate(CFSocketRef s)

    # CFStream
    ctypedef enum CFStreamErrorDomain:
        kCFStreamErrorDomainCustom = -1
        kCFStreamErrorDomainPOSIX = 1
        kCFStreamErrorDomainMacOSStatus = 2

    ctypedef struct CFStreamError:
        CFStreamErrorDomain domain
        int error

    cdef object CFObj_New(CFTypeRef)
    cdef int CFObj_Convert(object, CFTypeRef *)
    cdef object CFTypeRefObj_New(CFTypeRef)
    cdef int CFTypeRefObj_Convert(object, CFTypeRef *)
    cdef object CFStringRefObj_New(CFStringRef)
    cdef int CFStringRefObj_Convert(object, CFStringRef *)
    cdef object CFMutableStringRefObj_New(CFMutableStringRef)
    cdef int CFMutableStringRefObj_Convert(object, CFMutableStringRef *)
    cdef object CFArrayRefObj_New(CFArrayRef)
    cdef int CFArrayRefObj_Convert(object, CFArrayRef *)
    cdef object CFMutableArrayRefObj_New(CFMutableArrayRef)
    cdef int CFMutableArrayRefObj_Convert(object, CFMutableArrayRef *)
    cdef object CFDictionaryRefObj_New(CFDictionaryRef)
    cdef int CFDictionaryRefObj_Convert(object, CFDictionaryRef *)
    cdef object CFMutableDictionaryRefObj_New(CFMutableDictionaryRef)
    cdef int CFMutableDictionaryRefObj_Convert(object, CFMutableDictionaryRef *)
    cdef object CFURLRefObj_New(CFURLRef)
    cdef int CFURLRefObj_Convert(object, CFURLRef *)
    cdef int OptionalCFURLRefObj_Convert(object, CFURLRef *)
    
    # CFNetwork
    ctypedef struct CFNetServiceClientContext:
        CFIndex version
        void *info
        void *(*retain)(void *info)
        void (*release)(void *info)
        CFStringRef (*copyDescription)(void *info)

    ctypedef enum CFNetServiceBrowserClientCallBackFlags:
        kCFNetServiceFlagMoreComing = 1
        kCFNetServiceFlagIsDomain = 2
        kCFNetServiceFlagIsRegistrationDomain = 4
        kCFNetServiceFlagRemove = 8

    ctypedef CFTypeRef CFNetServiceBrowserRef
    ctypedef CFTypeRef CFNetServiceRef
    ctypedef void (*CFNetServiceBrowserClientCallBack)(CFNetServiceBrowserRef browser, CFOptionFlags flags, CFTypeRef domainOrService, CFStreamError* error, void* info)
    ctypedef void (*CFNetServiceClientCallBack)(CFNetServiceRef theService, CFStreamError* error, void* info)

    cdef CFNetServiceBrowserRef CFNetServiceBrowserCreate(CFAllocatorRef alloc, CFNetServiceBrowserClientCallBack clientCB, CFNetServiceClientContext* clientContext)
    cdef void CFNetworkServiceBrowserInvalidate(CFNetServiceBrowserRef browser)
    cdef void CFNetServiceBrowserScheduleWithRunLoop(CFNetServiceBrowserRef browser, CFRunLoopRef runLoop, CFStringRef runLoopMode)
    cdef Boolean CFNetServiceBrowserSearchForDomains(CFNetServiceBrowserRef browser, Boolean registrationDomain, CFStreamError* error)
    cdef Boolean CFNetServiceBrowserSearchForServices(CFNetServiceBrowserRef browser, CFStringRef domain, CFStringRef type, CFStreamError* error)
    cdef void CFNetServiceBrowserStopSearch(CFNetServiceBrowserRef browser, CFStreamError* error)

    # Call this function to shut down a browser that is running asynchronously.
    # To complete the shutdown, call CFNetServiceBrowserInvalidate followed by CFNetServiceBrowserStopSearch.
    cdef void CFNetServiceBrowserUnscheduleFromRunLoop(CFNetServiceBrowserRef browser, CFRunLoopRef runLoop, CFStringRef runLoopMode)

    cdef void CFNetServiceCancel(CFNetServiceRef theService)
    cdef CFNetServiceRef CFNetServiceCreate(CFAllocatorRef alloc, CFStringRef domain, CFStringRef type, CFStringRef name, unsigned int port)

    cdef CFArrayRef CFNetServiceGetAddressing(CFNetServiceRef theService)
    cdef CFStringRef CFNetServiceGetDomain(CFNetServiceRef theService)
    cdef CFStringRef CFNetServiceGetName(CFNetServiceRef theService)
    cdef CFStringRef CFNetServiceGetProtocolSpecificInformation(CFNetServiceRef theService)
    cdef CFStringRef CFNetServiceGetType(CFNetServiceRef theService)
    cdef Boolean CFNetServiceRegister(CFNetServiceRef theService, CFStreamError* error)
    cdef Boolean CFNetServiceResolve(CFNetServiceRef theService, CFStreamError* error)
    cdef void CFNetServiceScheduleWithRunLoop(CFNetServiceRef theService, CFRunLoopRef runLoop, CFStringRef runLoopMode)

    # For CFNetServices that will operate asynchronously, call this function and then call CFNetServiceScheduleWithRunLoop to schedule the service on a run loop. 
    # Then call CFNetServiceRegister or CFNetServiceResolve
    cdef Boolean CFNetServiceSetClient(CFNetServiceRef theService, CFNetServiceClientCallBack clientCB, CFNetServiceClientContext* clientContext)

    cdef void CFNetServiceSetProtocolSpecificInformation(CFNetServiceRef theService, CFStringRef theInfo)

    # Unschedules the specified service from the specified run loop and mode. 
    # Call this function to shut down a service that is running asynchronously. 
    # To complete the shutdown, call CFNetServiceSetClient and set clientCB to NULL. Then call CFNetServiceCancel.
    cdef void CFNetServiceUnscheduleFromRunLoop(CFNetServiceRef theService, CFRunLoopRef runLoop, CFStringRef runLoopMode)
