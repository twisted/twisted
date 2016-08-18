# -*- test-case-name: twisted.test.test_ssl -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module implements helpers for switching to TLS on an existing transport.

@since: 11.1
"""

class _TLSDelayed(object):
    """
    State tracking record for TLS startup parameters.  Used to remember how
    TLS should be started when starting it is delayed to wait for the output
    buffer to be flushed.

    @ivar bufferedData: A C{list} which contains all the data which was
        written to the transport after an attempt to start TLS was made but
        before the buffers outstanding at that time could be flushed and TLS
        could really be started.  This is appended to by the transport's
        write and writeSequence methods until it is possible to actually
        start TLS, then it is written to the TLS-enabled transport.

    @ivar context: An SSL context factory object to use to start TLS.

    @ivar extra: An extra argument to pass to the transport's C{startTLS}
        method.
    """
    def __init__(self, bufferedData, context, extra):
        self.bufferedData = bufferedData
        self.context = context
        self.extra = extra
