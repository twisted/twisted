# -*- coding: Latin-1 -*-

from twisted.python._c_dir import *

def isDirectory((name, type)):
    return type == DIR

def isCharDevice((name, type)):
    return type == CHR

def isBlockDevice((name, type)):
    return type == BLK

def isFifo((name, type)):
    return type == FIFO

def isRegularFile((name, type)):
    return type == REG

def isSymbolicLink((name, type)):
    return type == LNK

def isSocket((name, type)):
    return type == SOCK

def isWhiteout((name, type)):
    return type == WHT
