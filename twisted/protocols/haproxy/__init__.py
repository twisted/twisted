# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HAProxy PROXY protocol implementations.
"""

from ._exc import InvalidProxyHeader
from ._exc import InvalidNetworkProtocol
from ._exc import MissingAddressData

from ._info import ProxyInfo

from ._interfaces import IProxyInfo
from ._interfaces import IProxyParser

from ._v1parser import V1Parser

from ._v2parser import V2Parser

from ._wrapper import HAProxyProtocol
from ._wrapper import HAProxyFactory

__all__ = (
    'InvalidProxyHeader',
    'InvalidNetworkProtocol',
    'MissingAddressData',
    'ProxyInfo',
    'IProxyInfo',
    'IProxyParser',
    'V1Parser',
    'V2Parser',
    'HAProxyProtocol',
    'HAProxyFactory',
)
