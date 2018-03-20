#!/usr/bin/env python
#
# Copyright 2006-2009 Johann C. Rocholl <johann@rocholl.net>
# Copyright 2009-2014 Florent Xicluna <florent.xicluna@gmail.com>
# Copyright 2014-2018 Ian Lee <IanLee1521@gmail.com>

# Licensed under the terms of the Expat License

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
A patched version for pycodestyle which uses the blank line conversion from
Twisted.

Upstream integration is pending.
See https://github.com/PyCQA/pycodestyle/issues/732
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
    )

import re
import sys

import pycodestyle



def blank_lines(logical_line, blank_lines, indent_level, line_number,
                blank_before, previous_logical,
                previous_unindented_logical_line, previous_indent_level,
                lines):
    r"""Separate top-level function and class definitions with two blank lines.

    Method definitions inside a class are separated by a single blank line.

    Extra blank lines may be used (sparingly) to separate groups of related
    functions.  Blank lines may be omitted between a bunch of related
    one-liners (e.g. a set of dummy implementations).

    Use blank lines in functions, sparingly, to indicate logical sections.

    Okay: def a():\n    pass\n\n\ndef b():\n    pass
    Okay: def a():\n    pass\n\n\nasync def b():\n    pass
    Okay: def a():\n    pass\n\n\n# Foo\n# Bar\n\ndef b():\n    pass
    Okay: default = 1\nfoo = 1
    Okay: classify = 1\nfoo = 1

    E301: class Foo:\n    b = 0\n    def bar():\n        pass
    E302: def a():\n    pass\n\ndef b(n):\n    pass
    E302: def a():\n    pass\n\nasync def b(n):\n    pass
    E303: def a():\n    pass\n\n\n\ndef b(n):\n    pass
    E303: def a():\n\n\n\n    pass
    E304: @decorator\n\ndef a():\n    pass
    E305: def a():\n    pass\na()
    E306: def a():\n    def b():\n        pass\n    def c():\n        pass
    """
    top_level_lines = 3
    method_lines = 2
    if line_number < 3 and not previous_logical:
        return  # Don't expect blank lines before the first line
    if previous_logical.startswith('@'):
        if blank_lines:
            yield 0, "E304 blank lines found after function decorator"
    elif (
        (blank_lines > top_level_lines + 1) or
        (indent_level and blank_lines == method_lines + 1)
            ):
        yield 0, "E303 too many blank lines (%d)" % blank_lines
    elif pycodestyle.STARTSWITH_TOP_LEVEL_REGEX.match(logical_line):
        if indent_level:
            if not (blank_before or previous_indent_level < indent_level or
                    pycodestyle.DOCSTRING_REGEX.match(previous_logical)):
                ancestor_level = indent_level
                nested = False
                # Search backwards for a def ancestor or tree root (top level).
                for line in lines[line_number - 2::-1]:
                    if (
                        line.strip() and
                        pycodestyle.expand_indent(line) < ancestor_level
                            ):
                        ancestor_level = pycodestyle.expand_indent(line)
                        nested = line.lstrip().startswith('def ')
                        if nested or ancestor_level == 0:
                            break
                if nested:
                    yield 0, "E306 expected 1 blank line before a " \
                        "nested definition, found 0"
                else:
                    yield 0, "E301 expected 1 blank line, found 0"
        elif blank_before != top_level_lines:
            yield 0, "E302 expected %s blank lines, found %d" % (
                top_level_lines, blank_before)
    elif (
        logical_line and
        not indent_level and
        blank_before != top_level_lines and
        previous_unindented_logical_line.startswith(('def ', 'class '))
            ):
        yield 0, "E305 expected %s blank lines after " \
            "class or function definition, found %d" % (
                top_level_lines, blank_before)



# Replace the upstream blank_lines implementation, with our fork.
_previousValue = pycodestyle._checks['logical_line'][pycodestyle.blank_lines]
del pycodestyle._checks['logical_line'][pycodestyle.blank_lines]
pycodestyle._checks['logical_line'][blank_lines] = _previousValue



if __name__ == '__main__':
    # Calling main in a similar was as the upstream script.
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(pycodestyle._main())
