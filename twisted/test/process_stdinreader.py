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
"""Script used by twisted.test.test_process on win32."""

import sys, time, os, msvcrt
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)


sys.stdout.write("out\n")
sys.stdout.flush()
sys.stderr.write("err\n")
sys.stderr.flush()

data = sys.stdin.read()

sys.stdout.write(data)
sys.stdout.write("\nout\n")
sys.stderr.write("err\n")

sys.stdout.flush()
sys.stderr.flush()
