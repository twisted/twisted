# Paul, why didn't you check in an error.py?

"""An error to represent bad things happening in Conch.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

class ConchError(Exception):
    def __init__(self, value, data = None):
        Exception.__init__(self, value)
        self.data = data


