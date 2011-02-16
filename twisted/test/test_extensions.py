# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#

import os
from os.path import join as opj

from twisted.trial import unittest

from twisted.python import util


class CorrectComments(unittest.TestCase):
    def testNoSlashSlashComments(self):
        urlarg = util.sibpath(__file__, opj(os.pardir, 'protocols', '_c_urlarg.c'))
        contents = file(urlarg).read()
        self.assertEquals(contents.find('//'), -1)
