"""
Bindings for sendmsg(2), recvmsg(2), and a minimal helper for inspecting
address family of a socket.
"""

import os
import socket
import sys

import cffi

if sys.platform == "win32":
    raise ImportError("twisted.python.sendmsg is not available on Windows.")


def _type_for_width(width):
    return {
        1: "uint8_t",
        2: "uint16_t",
        4: "uint32_t",
        8: "uint64_t",
    }[width]


_configure_ffi = cffi.FFI()
_configure_ffi.cdef("""
static const size_t SIZEOF_SA_FAMILY;
static const size_t SIZEOF_CMSG_LEN;
""")
_configure_lib = _configure_ffi.verify("""
#include <sys/types.h>
#include <sys/socket.h>
#include <signal.h>

#include <sys/param.h>

#ifdef BSD
#  include <sys/uio.h>
#endif

#define member_size(type, member) sizeof(((type *)0)->member)

static const size_t SIZEOF_SA_FAMILY = member_size(struct sockaddr, sa_family);
static const size_t SIZEOF_CMSG_LEN = member_size(struct cmsghdr, cmsg_len);
""")

_ffi = cffi.FFI()
_ffi.cdef("""
const static int SCM_RIGHTS;

const static int SCM_CREDS;
const static bool HAS_SCM_CREDS;

const static int SCM_CREDENTIALS;
const static bool HAS_SCM_CREDENTIALS;

const static int SCM_TIMESTAMP;
const static bool HAS_SCM_TIMESTAMP;

struct iovec {
    char *iov_base;
    size_t iov_len;
};

struct msghdr {
    void *msg_name;
    int msg_namelen;
    struct iovec *msg_iov;
    unsigned msg_iovlen;
    void *msg_control;
    unsigned msg_controllen;
    unsigned msg_flags;
    ...;
};

struct cmsghdr {
    %(cmsg_len_type)s cmsg_level;
    int cmsg_type;
    unsigned cmsg_len;
    ...;
};

struct sockaddr {
    %(sa_family_type)s sa_family;
    ...;
};

ssize_t sendmsg(int, const struct msghdr *, int);
ssize_t recvmsg(int, struct msghdr *, int);

int getsockname(int, struct sockaddr *, size_t *);

size_t CMSG_SPACE(size_t);
size_t CMSG_LEN(size_t);
struct cmsghdr *CMSG_FIRSTHDR(struct msghdr *);
struct cmsghdr *CMSG_NXTHDR(struct msghdr *, struct cmsghdr *);
unsigned char *CMSG_DATA(struct cmsghdr *);
""" % {
    "cmsg_len_type": _type_for_width(_configure_lib.SIZEOF_CMSG_LEN),
    "sa_family_type": _type_for_width(_configure_lib.SIZEOF_SA_FAMILY),
})
_lib = _ffi.verify("""
#include <stdbool.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <signal.h>

#include <sys/param.h>

#ifdef BSD
#  include <sys/uio.h>
#endif

#if defined(SCM_CREDS)
    static const bool HAS_SCM_CREDS = true;
#else
    static const bool HAS_SCM_CREDS = false;
    static const int SCM_CREDS = -1;
#endif

#if defined(SCM_CREDENTIALS)
    static const bool HAS_SCM_CREDENTIALS = true;
#else
    static const bool HAS_SCM_CREDENTIALS = false;
    static const int SCM_CREDENTIALS = -1;
#endif

#if defined(SCM_TIMESTAMP)
    static const bool HAS_SCM_TIMESTAMP = true;
#else
    static const bool HAS_SCM_TIMESTAMP = false;
    static const int SCM_TIMESTAMP = -1;
#endif
""")
_SOCKLEN_MAX = 0x7FFFFFFF


SCM_RIGHTS = _lib.SCM_RIGHTS
if _lib.HAS_SCM_CREDS:
    SCM_CREDS = _lib.SCM_CREDS
if _lib.HAS_SCM_CREDENTIALS:
    SCM_CREDENTIALS = _lib.SCM_CREDENTIALS
if _lib.HAS_SCM_TIMESTAMP:
    SCM_TIMESTAMP = _lib.SCM_TIMESTAMP


def send1msg(fd, data, flags=0, ancillary=None):
    """
    Wrap the C sendmsg(2) function for sending "messages" on a socket.

    @param fd: The file descriptor of the socket over which to send a message.
    @type fd: C{int}

    @param data: Bytes to write to the socket.
    @type data: C{str}

    @param flags: Flags to affect how the message is sent.  See the C{MSG_}
        constants in the sendmsg(2) manual page.  By default no flags are set.
    @type flags: C{int}

    @param ancillary: Extra data to send over the socket outside of the normal
        datagram or stream mechanism.  By default no ancillary data is sent.
    @type ancillary: C{list} of C{tuple} of C{int}, C{int}, and C{str}.

    @raise OverflowError: Raised if too much ancillary data is given.
    @raise socket.error: Raised if the underlying syscall indicates an error.

    @return: The return value of the underlying syscall, if it succeeds.
    """
    data_ptr = _ffi.new("char[]", data)
    iov = _ffi.new("struct iovec[1]")
    iov[0].iov_base = data_ptr
    iov[0].iov_len = len(data)

    message_header = _ffi.new("struct msghdr *")
    message_header.msg_name = _ffi.NULL
    message_header.msg_namelen = 0
    message_header.msg_iov = iov
    message_header.msg_iovlen = 1
    message_header.msg_control = _ffi.NULL
    message_header.msg_controllen = 0
    message_header.msg_flags = 0

    if ancillary is not None:
        if not isinstance(ancillary, list):
            raise TypeError(
                "send1msg argument 3 expected list, got %s" % (
                    type(ancillary).__name__
                )
            )

        all_data_len = 0
        for item in ancillary:
            if not isinstance(item, tuple):
                raise TypeError(
                    "send1msg argument 3 expected list of tuple, got list "
                    "containing %s" % type(item).__name__
                )
            try:
                level, tp, data = item
            except ValueError:
                raise TypeError
            prev_all_data_len = all_data_len
            all_data_len += _lib.CMSG_SPACE(len(data))
            if int(_ffi.cast("size_t", all_data_len)) < prev_all_data_len:
                raise OverflowError(
                    "Too much msg_control to fit in a size_t: %d" % (
                        prev_all_data_len
                    )
                )

        if all_data_len:
            if all_data_len > _SOCKLEN_MAX:
                raise OverflowError(
                    "Too much msg_control to fit in a socklen_t: %d" % (
                        all_data_len
                    )
                )
            msg_control = _ffi.new("char[]", all_data_len)
            message_header.msg_control = msg_control
        else:
            message_header.msg_control = _ffi.NULL

        message_header.msg_controllen = all_data_len

        control_message = _lib.CMSG_FIRSTHDR(message_header)
        for level, tp, data in ancillary:
            control_message.cmsg_level = level
            control_message.cmsg_type = tp
            data_size = _lib.CMSG_LEN(len(data))

            if data_size > _SOCKLEN_MAX:
                raise OverflowError("CMSG_LEN(%zd) > SOCKLEN_MAX" % len(data))
            control_message.cmsg_len = data_size
            cmsg_data = _lib.CMSG_DATA(control_message)
            _ffi.buffer(cmsg_data, len(data))[:] = data
            control_message = _lib.CMSG_NXTHDR(message_header, control_message)

    sendmsg_result = _lib.sendmsg(fd, message_header, flags)

    if sendmsg_result < 0:
        raise socket.error(_ffi.errno, os.strerror(_ffi.errno))

    return sendmsg_result



def recv1msg(fd, flags=0, maxsize=8192, cmsg_size=4096):
    """
    Wrap the C recvmsg(2) function for receiving \"messages\" on a socket.

    @param fd: The file descriptor of the socket over which to receve a message.
    @type fd: C{int}

    @param flags: Flags to affect how the message is sent.  See the C{MSG_}
        constants in the sendmsg(2) manual page.  By default no flags are set.
    @type flags: C{int}

    @param maxsize: The maximum number of bytes to receive from the socket
        using the datagram or stream mechanism.  The default maximum is 8192.
    @type maxsize: C{int}

    @param cmsg_size: The maximum number of bytes to receive from the socket
        outside of the normal datagram or stream mechanism.  The default maximum is 4096.

    @raise OverflowError: Raised if too much ancillary data is given.
    @raise socket.error: Raised if the underlying syscall indicates an error.

    @return: A C{tuple} of three elements: the bytes received using the
        datagram/stream mechanism, flags as an C{int} describing the data
        received, and a C{list} of C{tuples} giving ancillary received data.
    """
    cmsg_space = _lib.CMSG_SPACE(cmsg_size)
    if cmsg_space > _SOCKLEN_MAX:
        raise OverflowError(
            "CMSG_SPACE(cmsg_size) greater than SOCKLEN_MAX: %d" % cmsg_size
        )

    message_header = _ffi.new("struct msghdr *")
    message_header.msg_name = _ffi.NULL
    message_header.msg_namelen = 0

    iov = _ffi.new("struct iovec[1]")
    data_ptr = _ffi.new("char[]", maxsize)
    iov[0].iov_len = maxsize
    iov[0].iov_base = data_ptr

    message_header.msg_iov = iov
    message_header.msg_iovlen = 1

    cmsgbuf = _ffi.new("char[]", cmsg_space)
    message_header.msg_control = cmsgbuf
    message_header.msg_controllen = cmsg_space

    recvmsg_result = _lib.recvmsg(fd, message_header, flags)
    if recvmsg_result < 0:
        raise socket.error(_ffi.errno, os.strerror(_ffi.errno))

    ancillary = []
    control_message = _lib.CMSG_FIRSTHDR(message_header)
    while control_message != _ffi.NULL:
        # Some platforms apparently always fill out the ancillary data
        # structure with a single bogus value if none is provided; ignore it,
        # if that is the case.
        if control_message.cmsg_level or control_message.cmsg_type:
            cmsg_overhead = _lib.CMSG_DATA(control_message) - _ffi.cast("unsigned char *", control_message)
            entry = (
                control_message.cmsg_level,
                control_message.cmsg_type,
                _ffi.buffer(_lib.CMSG_DATA(control_message), control_message.cmsg_len - cmsg_overhead)[:]
            )
            ancillary.append(entry)


        control_message = _lib.CMSG_NXTHDR(message_header, control_message)

    return (
        _ffi.buffer(data_ptr, recvmsg_result)[:],
        message_header.msg_flags,
        ancillary
    )


def getsockfam(fd):
    """
    Retrieve the address family of a given socket.

    @param fd: The file descriptor of the socket the address family of which
        to retrieve.
    @type fd: C{int}

    @raise socket.error: Raised if the underlying getsockname call indicates
        an error.

    @return: A C{int} representing the address family of the socket.  For
        example, L{socket.AF_INET}, L{socket.AF_INET6}, or L{socket.AF_UNIX}.

    """
    sa = _ffi.new("struct sockaddr *")
    sz = _ffi.new("size_t *", _ffi.sizeof("struct sockaddr"))
    res = _lib.getsockname(fd, sa, sz)
    if res:
        raise socket.error(_ffi.errno, os.strerror(_ffi.errno))
    return sa.sa_family
