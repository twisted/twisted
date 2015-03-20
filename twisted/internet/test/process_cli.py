import sys, os
try:
    # On Windows, stdout is not opened in binary mode by default,
    # so newline characters are munged on writing, interfering with
    # the tests.
    import msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
except ImportError:
    pass

if sys.version_info < (3, 0):
    _PY3 = False
else:
    _PY3 = True

if _PY3:
    stdout = sys.stdout.buffer
else:
    stdout = sys.stdout

for arg in sys.argv[1:]:

    res = arg + chr(0)

    if _PY3:
        stdout.write(res.encode("utf8", "surrogateescape"))
    else:
        stdout.write(res)

    stdout.flush()
