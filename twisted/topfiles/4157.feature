If returnValue is invoked outside of a function decorated with
@inlineCallbacks, but causes a function thusly decorated to exit, a
DeprecationWarning will be emitted explaining this potentially confusing
behavior.  In a future release, this will cause an exception.
