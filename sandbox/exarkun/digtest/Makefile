CC=gcc -I.

default: all

all:	mdriver digcalc

mdriver: md5.o mdriver.o
	$(CC) -o mdriver md5.o mdriver.o
	
mdriver.o:  mdriver.c
	$(CC) -c mdriver.c  
	
digcalc: digtest.o digcalc.o md5.o
	$(CC) -o digcalc digtest.o digcalc.o md5.o

digcalc.o: digcalc.c
	$(CC) -c digcalc.c

digtest.o: digtest.c
	$(CC) -c digtest.c
	
md5.o: md5.c
	$(CC) -c md5.c
