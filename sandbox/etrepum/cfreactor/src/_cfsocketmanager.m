#import <CoreFoundation/CoreFoundation.h>
#import <Foundation/Foundation.h>
#import "Python.h"
#import "_cfsocketmanager.h"

@implementation CFSocketDelegate

-(void)writeCallBackWithSocket:(CFSocketRef)s
{
}

-(void)readCallBackWithSocket:(CFSocketRef)s
{
}

@end

static void _socketManagerCallBack(CFSocketRef s, CFSocketCallBackType _type, CFDataRef address, const void *data, void *info)
{
    [(CFSocketManager*)info callBackWithCFSocketRef:s ofType:_type withAddress:address data:data];
}

@implementation CFSocketManager
-init
{
	self = [super init];
	if (self != nil) {
		delegate = nil;
	}
    context.version = 0;
    context.info = (void *)self;
    context.retain = NULL;
    context.release = NULL;
    context.copyDescription = NULL;
	return self;
}

-(CFSocketRef)createSocketWithNativeHandle:(CFSocketNativeHandle)fileno flags:(CFOptionFlags)flags
{
	return CFSocketCreateWithNative(kCFAllocatorDefault, fileno, flags, &_socketManagerCallBack, &context);
}

-(void)callBackWithCFSocketRef:(CFSocketRef)s ofType:(CFSocketCallBackType)callbackType withAddress:(CFDataRef)address data:(const void *)data
{
    if (callbackType == kCFSocketReadCallBack) {
        [[self delegate] readCallBackWithSocket:s];
    } else if (callbackType == kCFSocketWriteCallBack) {
        [[self delegate] writeCallBackWithSocket:s];
    }
}

-(void)setDelegate:(CFSocketDelegate*)_delegate
{
    [_delegate retain];
    [delegate release];
    delegate = _delegate;
}

-(CFSocketDelegate*)delegate
{
    return delegate;
}

-(void)dealloc
{
    [self setDelegate:nil];
    [super dealloc];
}

@end


static struct PyMethodDef __cfsocketmanager_methods[] = {
	{0, 0, 0, 0}
};

DL_EXPORT(void) init_cfsocketmanager(void) {
	PyObject *mod = Py_InitModule4("_cfsocketmanager", __cfsocketmanager_methods, 0, 0, PYTHON_API_VERSION);
	PyModule_AddStringConstant(mod, "__version__", "0.1");
	return;
}
