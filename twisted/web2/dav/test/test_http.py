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

import errno

from twisted.python.failure import Failure
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError
from twisted.web2.dav.http import ErrorResponse, statusForFailure
import twisted.web2.dav.test.util

class HTTP(twisted.web2.dav.test.util.TestCase):
    """
    HTTP Utilities
    """
    def test_statusForFailure_errno(self):
        """
        statusForFailure() for exceptions with known errno values
        """
        for ex_class in (IOError, OSError):
            for exception, result in (
                (ex_class(errno.EACCES, "Permission denied" ), responsecode.FORBIDDEN),
                (ex_class(errno.EPERM , "Permission denied" ), responsecode.FORBIDDEN),
                (ex_class(errno.ENOSPC, "No space available"), responsecode.INSUFFICIENT_STORAGE_SPACE),
                (ex_class(errno.ENOENT, "No such file"      ), responsecode.NOT_FOUND),
            ):
                self._check_exception(exception, result)

    def test_statusForFailure_HTTPError(self):
        """
        statusForFailure() for HTTPErrors
        """
        for code in responsecode.RESPONSES:
            self._check_exception(HTTPError(code), code)
            self._check_exception(HTTPError(ErrorResponse(code, ("http://twistedmatrix.com/", "bar"))), code)

    def test_statusForFailure_exception(self):
        """
        statusForFailure() for known/unknown exceptions
        """
        for exception, result in (
            (NotImplementedError("Duh..."), responsecode.NOT_IMPLEMENTED),
        ):
            self._check_exception(exception, result)

        class UnknownException (Exception):
            pass

        try:
            self._check_exception(UnknownException(), None)
        except UnknownException:
            pass
        else:
            self.fail("Unknown exception should have re-raised.")

    def _check_exception(self, exception, result):
        try:
            raise exception
        except Exception, e:
            failure = Failure()
            status = statusForFailure(failure)
            self.failUnless(
                status == result,
                "Failure %r (%s) generated incorrect status code: %s != %s"
                % (failure, failure.value, status, result)
            )
        else:
            raise AssertionError("We shouldn't be here.")
