from cffi import FFI

import errno
import os
import sys

ffi = FFI()

if ffi.sizeof("long") == 4:
    ffi.cdef("""
    typedef long long off_t;
""")
else:
    ffi.cdef("""
    typedef long off_t;
""")

if sys.platform == "darwin":
    ffi.cdef("""
int
    sendfile(int fd, int s, off_t offset, off_t *len, struct sf_hdtr *hdtr,
             int flags);
""")
    libc = ffi.verify("""
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>
""")

    def sendfile(out_fd, in_fd, offset, nbytes):
        length = ffi.new("off_t *", nbytes)
        ret = libc.sendfile(in_fd, out_fd, offset, length, ffi.NULL, 0)
        if ret < 0:
            if length[0] and not ffi.errno in (errno.EBUSY, errno.EAGAIN,
                                               errno.EWOULDBLOCK):
                raise OSError(os.strerror(ffi.errno))
        return length[0]

elif "linux" in sys.platform:
    ffi.cdef("""
ssize_t
    sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
""")
    libc = ffi.verify("""
#include <sys/sendfile.h>
""")

    def sendfile(out_fd, in_fd, offset, nbytes):
        off_t = ffi.new("off_t *", offset)
        sent = libc.sendfile(out_fd, in_fd, off_t, nbytes)
        if sent == -1:
            raise OSError(os.strerror(ffi.errno))
        return sent
else:
    # BSD fallback
    ffi.cdef("""
int
    sendfile(int fd, int s, off_t offset, size_t nbytes,
             struct sf_hdtr *hdtr, off_t *sbytes, int flags);
""")
    libc = ffi.verify("""
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>
""")

    def sendfile(out_fd, in_fd, offset, nbytes):
        sbytes = ffi.new("off_t *")
        ret = libc.sendfile(in_fd, out_fd, offset, nbytes, ffi.NULL, sbytes, 0)
        if ret < 0:
            if sbytes[0] and not ffi.errno in (errno.EBUSY, errno.EAGAIN,
                                               errno.EWOULDBLOCK):
                raise OSError(os.strerror(ffi.errno))
        return sbytes[0]

