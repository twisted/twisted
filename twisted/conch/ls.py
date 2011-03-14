# -*- test-case-name: twisted.conch.test.test_cftp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import array
import stat

from time import time, strftime, localtime

# locale-independent month names to use instead of strftime's
MONTH_NAMES = dict(zip(range(1, 13),
                   "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()))


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

    un = str(s.st_uid)
    gr = str(s.st_gid)
    sz = str(s.st_size)
    sixmo = 60 * 60 * 24 * 7 * 26
    l = [perms.tostring(), str(s.st_nlink).rjust(5), ' ',
         un.ljust(9), gr.ljust(9), sz.rjust(8), ' ']

    # need to specify the month manually, as strftime depends on locale
    ttup = localtime(s.st_mtime)
    if s.st_mtime + sixmo < time(): # last edited more than 6mo ago
        strtime = strftime("%%s %d  %Y ", ttup)
    else:
        strtime = strftime("%%s %d %H:%M ", ttup)
    l.append(strtime % (MONTH_NAMES[ttup[1]],))

    l.append(name)
    return ''.join(l)


__all__ = ['lsLine']
