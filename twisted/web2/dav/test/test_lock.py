##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

from twisted.trial.unittest import SkipTest
import twisted.web2.dav.test.util

class LOCK_UNLOCK(twisted.web2.dav.test.util.TestCase):
    """
    LOCK, UNLOCK requests
    """
    # FIXME:
    # Check PUT
    # Check POST
    # Check PROPPATCH
    # Check LOCK
    # Check UNLOCK
    # Check MOVE, COPY
    # Check DELETE
    # Check MKCOL
    # Check null resource
    # Check collections
    # Check depth
    # Check If header
    # Refresh lock

    def test_LOCK_UNLOCK(self):
        """
        LOCK, UNLOCK request
        """
        raise SkipTest("test unimplemented")

    test_LOCK_UNLOCK.todo = "LOCK/UNLOCK unimplemented"
