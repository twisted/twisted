
all: event.c
	python setup.py build

event.c: event.pyx
	pyrexc event.pyx

install:
	python setup.py install

clean:
	rm -rf build

quick:
	 pyrexc event.pyx 
	 gcc -fPIC -c -I/usr/include/python2.3 event.c
	 gcc -shared event.o -levent -o event.so

cleandir distclean: clean
	rm -f *.c *~
