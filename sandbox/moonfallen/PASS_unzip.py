from __future__ import generators

import zipfile
from path import path


DIR_BIT=16
def unzip(filename, directory=".", overwrite=0, generator=1):
    """Unzip the file
    @param filename: the name of the zip file
    @param directory: the directory into which the files will be extracted
    """
    zf=zipfile.ZipFile(filename, 'r')
    names=zf.namelist()
    remaining=count=len(names)
    for entry in names:
        remaining=remaining-1
        isdir=zf.getinfo(entry).external_attr & DIR_BIT
        f=(path(directory)/entry).abspath()
        fdir=f.dirname()
        try:
            fdir.makedirs()
        except OSError, e:
            if e.args[1]=='File exists':
                pass
            else:
                raise e

        if isdir and not f.exists():
            f.mkdir()
        elif (overwrite or not f.exists()):
            outfile=file(f, 'wb')
            outfile.write(zf.read(entry))
            outfile.close()
        if generator:
            yield remaining
