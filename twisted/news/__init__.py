# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


"""

Twisted News: an NNTP-based news service.

This package is DEPRECATED. It has been split off into a third party
package. Please see http://projects.twistedmatrix.com/news.

This is just a place-holder that imports from the third-party news
package for backwards compatibility. To use it, you need to install
the third-party news package.

"""


try:
    from lowdown import news
    from lowdown import database
except ImportError:
    raise ImportError("You need to have the third-party news package installed to use twisted.news. See http://projects.twistedmatrix.com/news.")

# I'll put this *after* the imports, because if there's an error,
# they'll see a similar message anyway. And this way, tests can try to
# import the module and skip if it's not found, with no warning.

import warnings
warnings.warn("twisted.news is DEPRECATED. See http://projects.twistedmatrix.com/news.", DeprecationWarning)
