"""
This module has a deprecated module attribute.
"""


from incremental import Version

from twisted.python.deprecate import deprecatedModuleAttribute

oldVersion = Version("Bar", 1, 2, 3)


def somethingOld() -> None:
    """
    A deprecated module attribute. Used by
    L{GetDeprecatedModuleAttributeTests.test_deprecated}.
    """


# A non-deprecated alias of _somethingOld.
_somethingOld = somethingOld


deprecatedModuleAttribute(
    oldVersion,
    "It's old and clunky",
    __name__,
    "somethingOld",
)


def somethingNew() -> None:
    """
    A module attribute that is not deprecated. Used by
    L{GetDeprecatedModuleAttributeTests.test_notDeprecated}.
    """
