all: lint banana.html

lint: banana.xhtml
	-lore -n --output lint $<
banana.html: banana.xhtml
	lore -p --config template=../../doc/howto/template.tpl \
		--config ext=.html $<

TEST=test_banana test_schema test_pb
test:
	../../bin/trial -v $(TEST)
test2:
	../../bin/trial -o $(TEST)

clean:
	rm -f *~ *.pyc *.xhtml
	rm -rf _trial_temp
