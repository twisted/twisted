
test: libevent.so
	#python testevent.py
	echo "done."

libevent.so: libevent.c
	gcc -o libevent.o -pthread -fPIC -I/usr/include/python2.3 -c libevent.c -g
	ld -o libevent.so libevent.o -shared -levent -lpython2.3

libevent.c: libevent.pyx
	pyrexc libevent.pyx

clean:
	rm -rf *~ *.pyc libevent.c libevent.so libevent.o build
