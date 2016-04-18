from sys import stdout
from os import environ
items = environ.items()
stdout.write(chr(0).join([k + chr(0) + v for k, v in items]))
stdout.flush()
