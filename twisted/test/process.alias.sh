#!/bin/sh

rm -f process.alias.out
while read i; do
	echo $i >> process.alias.out
done
