"""Test to make sure we can open /dev/tty"""

f = open("/dev/tty", "rb+")
a = f.readline()
f.write(a)
f.close()
