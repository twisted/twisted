# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

from twisted.lore import book
import sys

def run():
    book.doFile(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    run()

