"""Test to make sure we can open /dev/tty"""

f = open("/dev/tty", "r+")
a = f.readline()
f.write(a)
f.close()
