# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Persisted: utilities for managing persistence.
"""


from twisted.python import versions, deprecate

deprecate.deprecatedModuleAttribute(versions.Version('twisted', 11, 0, 0),
                                    "Use a different persistence library. This one "
                                    "is no longer maintained.",
                                    __name__, 'journal')

