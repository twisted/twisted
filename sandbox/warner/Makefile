all: lint banana.xhtml

lint: banana.html
	-lore -n --output lint $<
banana.xhtml: banana.html
	lore -p --config template=../../doc/howto/template.tpl $<

test:
	../../bin/trial -v test_banana test_schema

clean:
	rm -f *~ *.pyc *.xhtml
	rm -rf _trial_temp
