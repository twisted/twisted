# useful general C stuff
ctypedef int ssize_t
ctypedef unsigned int size_t

# forward declaration
cdef class CProtocol

cdef class Buffer:
    cdef void (*dealloc)(void*)
    cdef char* buffer
    cdef int buflen

    cdef init(self, void (*deallocator)(void*), char* buffer, int buflen)
    cdef __dealloc__(self)
    cdef __getreadbuffer__(self, int segment, void **ptrptr)
    cdef __getsegcount__(self, int *lenp)


cdef public class _CMixin [object TwistedTransport, type TwistedTransportType]:
    cdef char* _c_buffer
    cdef size_t _c_buflen
    cdef CProtocol cprotocol
    cdef int _c_socketfd

    cdef void setReadBuffer(self, char* buffer, size_t buflen)


cdef class CProtocol:
    cdef _CMixin ctransport
    cdef object transport # for ref counting

    cdef void cdataReceived(self, char* buffer, int buflen)
    cdef void cbufferFull(self)

