from __future__ import generators

import zipfile
import os.path


DIR_BIT=16
def unzip(filename, directory=".", overwrite=0):
    """Unzip the file
    @param filename: the name of the zip file
    @param directory: the directory into which the files will be
    extracted
    @param overwrite: if on, overwrite files when they exist.  You can
    still get an error if you try to create a directory over a file
    with the same name or vice-versa.
    @param generator: yield after every file
    """
    for i in unzipiter(filename, directory, overwrite):
        pass

def unzipiter(filename, directory='.', overwrite=0):
    zf=zipfile.ZipFile(filename, 'r')
    names=zf.namelist()
    if not os.path.exists(directory): os.makedirs(directory)
    remaining=len(names)
    for entry in names:
        remaining=remaining - 1
        isdir=zf.getinfo(entry).external_attr & DIR_BIT
        f=os.path.join(directory, entry)
        if isdir:
            # overwrite flag only applies to files
            if not os.path.exists(f): os.makedirs(f)
        else:
            # create the directory the file will be in first,
            # since we can't guarantee it exists
            fdir=os.path.split(f)[0]
            if not os.path.exists(fdir):
                os.makedirs(f)
            if overwrite or not os.path.exists(f):
                outfile=file(f, 'wb')
                outfile.write(zf.read(entry))
                outfile.close()
        yield remaining

