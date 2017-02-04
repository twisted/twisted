# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Compat shim imports.
"""

from iocpreactor import (
    _abstract as abstract,
    _const as const,
    _interfaces as interfaces,
    _reactor as reactor,
    _tcp as tcp,
    _udp as udp,
    _iocpsupport as iocpsupport
)



__all__ = ["abstract", "const", "interfaces", "reactor", "tcp", "udp",
           "iocpsupport"]
