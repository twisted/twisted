_FUNCTIONS = [
    ('CFRelease', 'v@'),
    ('CFAbsoluteTimeGetCurrent', 'd'),
    ('CFRunLoopGetCurrent', '@'),
    ('CFRunLoopStop', 'v@'),
    ('CFRunLoopCopyCurrentMode', '@@'),
    ('CFRunLoopAddSource', 'v@@@'),
    ('CFRunLoopRemoveSource', 'v@@@'),
    ('CFSocketInvalidate', 'v@'),
    ('CFSocketDisableCallBacks', 'v@i'),
    ('CFSocketEnableCallbacks', 'v@i'),
    ('CFSocketSetSocketFlags', 'v@i'),
    ('CFSocketCreateRunLoopSource', '@@@i'),
    # CFSocketCreateWithNative
]
_VARIABLES = (
    [(_v, '@') for _v in [
        'kCFAllocatorDefault', 'kCFAllocatorNull',
        'kCFRunLoopCommonModes',
    ]]
)
    
kCFSocketAutomaticallyReenableReadCallBack = 1
kCFSocketAutomaticallyReenableAcceptCallBack = 2
kCFSocketAutomaticallyReenableDataCallBack = 3
kCFSocketAutomaticallyReenableWriteCallBack = 8
kCFSocketCloseOnInvalidate = 128
kCFSocketNoCallBack = 0
kCFSocketReadCallBack = 1
kCFSocketAcceptCallBack = 2
kCFSocketDataCallBack = 3
kCFSocketConnectCallBack = 4
kCFSocketWriteCallBack = 8

def _initialize(g):
    import objc
    bndl = objc.loadBundle(
        'CoreFoundation',
        g,
        bundle_identifier=u'com.apple.CoreFoundation')
    objc.loadBundleFunctions(
        bndl,
        g,
        _FUNCTIONS)
    objc.loadBundleVariables(
        bndl,
        g,
        _VARIABLES)
_initialize(globals())
