Extremely Low-Level Socket Operations
=====================================

Introduction
------------

Beyond supporting streams of data (SOCK_STREAM) or datagrams (SOCK_DGRAM), POSIX sockets have additional features not accessible via send(2) and recv(2).
These features include things like scatter/gather I/O, duplicating file descriptors into other processes, and accessing out-of-band data.

Twisted includes a wrapper around the two C APIs which make these things possible, `sendmsg <http://www.opengroup.org/onlinepubs/007908799/xns/sendmsg.html>`_ and `recvmsg <http://www.opengroup.org/onlinepubs/007908799/xns/recvmsg.html>`_ .
This document covers their usage.
It is intended for Twisted maintainers.
Application developers looking for this functionality should look for the high-level APIs Twisted provides on top of these wrappers.


sendmsg
~~~~~~~

``sendmsg(2)`` exposes nearly all sender-side functionality of a socket.
For a SOCK_STREAM socket, it can send bytes that become part of the stream of data being carried over the connection.
For a SOCK_DGRAM socket, it can send bytes that become datagrams sent from the socket.
It can send data from multiple memory locations (gather I/O).
Over AF_UNIX sockets, it can copy file descriptors into whichever process is receiving on the other side.
The wrapper included in Twisted, :api:`twisted.python.sendmsg.sendmsg <sendmsg>`, exposes many (but not all) of these features.
This document covers the usage of the features it does expose.
The primary limitation of this wrapper is that the interface supports sending only one *iovec* at a time.


recvmsg
~~~~~~~

Likewise, ``recvmsg(2)`` exposes nearly all the receiver-side functionality of a socket.
It can receive stream data over from a SOCK_STREAM socket or datagrams from a SOCK_DGRAM socket.
It can receive that data into multiple memory locations (scatter I/O), and it can receive those copied file descriptors.
The wrapper included in Twisted, :api:`twisted.python.sendmsg.recvmsg <recvmsg>`, exposes many (but not all) of these features.
This document covers the usage of the features it does expose.
The primary limitation of this wrapper is that the interface supports receiving only one *iovec* at a time.


Sending And Receiving Regular Data
----------------------------------

sendmsg can be used in a way which makes it equivalent to using the send call.
The first argument to sendmsg is (in this case and all others) a socket over which to send the data.
The second argument is a bytestring giving the data to send.

On the other end, recvmsg can be used to replace a recv call.
The first argument to recvmsg is (again, in all cases) a socket over which to receive the data.
The second argument is an integer giving the maximum number of bytes of data to receive.

:download:`send_replacement.py <listings/sendmsg/send_replacement.py>`

.. literalinclude:: listings/sendmsg/send_replacement.py


Copying File Descriptors
------------------------

Used with an AF_UNIX socket, sendmsg send a copy of a file descriptor into whatever process is receiving on the other end of the socket.
This is done using the ancillary data argument.
Ancillary data consists of a list of three-tuples.
A three-tuple constructed with SOL_SOCKET, SCM_RIGHTS, and a platform-endian packed file descriptor number will copy that file descriptor.

File descriptors copied this way must be received using a recvmsg call.
No special arguments are required to receive these descriptors.
They will appear, encoded as a native-order string, in the ancillary data list returned by recvmsg.

:download:`copy_descriptor.py <listings/sendmsg/copy_descriptor.py>`

.. literalinclude:: listings/sendmsg/copy_descriptor.py
