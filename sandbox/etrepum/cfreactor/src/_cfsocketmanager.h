@interface CFSocketDelegate : NSObject
{
}
-(void)writeCallBackWithSocket:(CFSocketRef)s;
-(void)readCallBackWithSocket:(CFSocketRef)s;
@end

@interface CFSocketManager : NSObject
{
	CFSocketDelegate* delegate;
    CFSocketContext context;
}
-(void)setDelegate:(CFSocketDelegate*)delegate;
-(CFSocketDelegate*)delegate;
-(void)callBackWithCFSocketRef:(CFSocketRef)s ofType:(CFSocketCallBackType)callbackType withAddress:(CFDataRef)address data:(const void *)data;
-(CFSocketRef)createSocketWithNativeHandle:(CFSocketNativeHandle)fileno flags:(CFOptionFlags)flags;
@end
