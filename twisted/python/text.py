
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

"""Miscellany of text-munging functions.
"""

import string

def greedyWrap(inString, width=80):
    """Given a string and a column width, return a list of lines.

    Caveat: I'm use a stupid greedy word-wrapping
    algorythm.  I won't put two spaces at the end
    of a sentence.  I don't do full justification.
    And no, I've never even *heard* of hypenation.
    """

    outLines = []

    inWords = string.split(inString)

    column = 0
    ptr_line = 0
    while inWords:
        column = column + len(inWords[ptr_line])
        ptr_line = ptr_line + 1

        if (column > width):
            if ptr_line == 1:
                # This single word is too long, it will be the whole line.
                pass
            else:
                # We've gone too far, stop the line one word back.
                ptr_line = ptr_line - 1
            (l, inWords) = (inWords[0:ptr_line], inWords[ptr_line:])
            outLines.append(string.join(l,' '))

            ptr_line = 0
            column = 0
        elif not (len(inWords) > ptr_line):
            # Clean up the last bit.
            outLines.append(string.join(inWords, ' '))
            del inWords[:]
        else:
            # Space
            column = column + 1
    # next word

    return outLines


wordWrap = greedyWrap
