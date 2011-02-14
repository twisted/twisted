# -*- test-case-name: twisted.conch.test.test_cftp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import array
import stat

from time import time, strftime, localtime


def lsLine(name, s):
    mode = s.st_mode
    perms = array.array('c', '-'*10)
    ft = stat.S_IFMT(mode)
    if stat.S_ISDIR(ft): perms[0] = 'd'
    elif stat.S_ISCHR(ft): perms[0] = 'c'
    elif stat.S_ISBLK(ft): perms[0] = 'b'
    elif stat.S_ISREG(ft): perms[0] = '-'
    elif stat.S_ISFIFO(ft): perms[0] = 'f'
    elif stat.S_ISLNK(ft): perms[0] = 'l'
    elif stat.S_ISSOCK(ft): perms[0] = 's'
    else: perms[0] = '!'
    # user
    if mode&stat.S_IRUSR:perms[1] = 'r'
    if mode&stat.S_IWUSR:perms[2] = 'w'
    if mode&stat.S_IXUSR:perms[3] = 'x'
    # group
    if mode&stat.S_IRGRP:perms[4] = 'r'
    if mode&stat.S_IWGRP:perms[5] = 'w'
    if mode&stat.S_IXGRP:perms[6] = 'x'
    # other
    if mode&stat.S_IROTH:perms[7] = 'r'
    if mode&stat.S_IWOTH:perms[8] = 'w'
    if mode&stat.S_IXOTH:perms[9] = 'x'
    # suid/sgid
    if mode&stat.S_ISUID:
        if perms[3] == 'x': perms[3] = 's'
        else: perms[3] = 'S'
    if mode&stat.S_ISGID:
        if perms[6] == 'x': perms[6] = 's'
        else: perms[6] = 'S'
    l = perms.tostring()
    l += str(s.st_nlink).rjust(5) + ' '
    un = str(s.st_uid)
    l += un.ljust(9)
    gr = str(s.st_gid)
    l += gr.ljust(9)
    sz = str(s.st_size)
    l += sz.rjust(8)
    l += ' '
    sixmo = 60 * 60 * 24 * 7 * 26
    if s.st_mtime + sixmo < time(): # last edited more than 6mo ago
        l += strftime("%b %d  %Y ", localtime(s.st_mtime))
    else:
        l += strftime("%b %d %H:%M ", localtime(s.st_mtime))
    l += name
    return l


__all__ = ['lsLine']
