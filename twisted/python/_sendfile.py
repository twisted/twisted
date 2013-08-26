from cffi import FFI

import os

ffi = FFI()

if ffi.sizeof("long") == 4:
    ffi.cdef("""
    typedef long long off_t;
""")
else:
    ffi.cdef("""
    typedef long off_t;
""")

ffi.cdef("""
    ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
""")

libc = ffi.dlopen(None)


#print ffi.sizeof("long")
def sendfile(out_fd, in_fd, offset, nbytes):
    off_t = ffi.new("off_t *")
    off_t[0] = offset
    sent = libc.sendfile(out_fd, in_fd, off_t, nbytes)
    if sent == -1:
        raise OSError(os.strerror(ffi.errno))
    return sent
