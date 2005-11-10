# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Utilities for dealing with processes.

@stability: Unstable
"""

import os

def which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.
    
    @type name: C{str}
    @param name: The name for which to search.
    
    @type flags: C{int}
    @param flags: Arguments to L{os.access}.
    
    @rtype: C{list}
    @param: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    for p in os.environ['PATH'].split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)
    return result

