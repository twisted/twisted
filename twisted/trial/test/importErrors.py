"""This module intentionally fails to import.

See twisted.trial.test.test_adapters.TestFailureFormatting.testImportError
"""
# Log where we were imported from, to help debugging.
from twisted.python import log
import traceback
from StringIO import StringIO
buf = StringIO()
traceback.print_stack(file=buf)
log.msg('importErrors imported from:')
log.msg(buf.getvalue())

# Import a module that doesn't exist.  Boom!
import Supercalifragilisticexpialidocious

from twisted.trial.test import common

class ThisTestWillNeverSeeTheLightOfDay(common.BaseTest, unittest.TestCase):
    pass


