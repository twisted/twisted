#!/usr/bin/env python2.3 

import os


#def recursive_rename (folder):
#    for name in os.listdir (folder):
#        if name[0] == ".": continue
#        some_processing_on (folder + "/" + name)
#    for name in os.listdir (folder):
#        fpath = (folder + "/" + name)
#        if name[0] == ".": continue
#        if os.path.isdir (fpath):
#            recursive_rename (fpath)
#recursive_rename (".")

root = '/home/jonathan/src'


def recurse_tree(folder, adict):
    for name in os.listdir(folder):
        if name[0] == '.':
            continue
    for name in os.listdir





