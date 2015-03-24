import sys, os
try:
    # On Windows, stdout is not opened in binary mode by default,
    # so newline characters are munged on writing, interfering with
    # the tests.
    import msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
except ImportError:
    pass


for arg in sys.argv[1:]:
    res = arg + chr(0)

    if sys.version_info < (3, 0):
        stdout = sys.stdout
    else:
        res = res.encode("utf8", "surrogateescape")
        stdout = sys.stdout.buffer

    stdout.write(res)
    stdout.flush()
