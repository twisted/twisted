# -*- test-case-name: twisted.test.test_internet -*-
# $Id: default.py,v 1.90 2004/01/06 22:35:22 warner Exp $
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Deprecated module that used to contain SelectReactor and PosixReactorBase

Maintainer: Itamar Shtull-Trauring
"""

import warnings
warnings.warn("twisted.internet.default is deprecated. Use posixbase or selectreactor instead.", category=DeprecationWarning)

# Backwards compat
from posixbase import PosixReactorBase
from selectreactor import SelectReactor, install

__all__ = ["install", "PosixReactorBase", "SelectReactor"]
