# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HAProxy PROXY protocol implementations.
"""

from ._wrapper import HAProxyProtocolWrapper
from ._wrapper import HAProxyWrappingFactory

__all__ = (
    'HAProxyProtocolWrapper',
    'HAProxyWrappingFactory',
)
