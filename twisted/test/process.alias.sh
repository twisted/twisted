#!/bin/bash

echo "FOOOG" > /tmp/PROCESS.ALIAS

rm -f process.alias.out
while read i; do
	echo $i >> process.alias.out
done

echo "EXITTTTEDD" >> /tmp/PROCESS.ALIAS