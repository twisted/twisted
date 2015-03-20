"""Test to make sure we can open /dev/tty"""

f = open("/dev/tty", "rb+", buffering=0)
a = f.readline()
f.write(a)
f.close()
