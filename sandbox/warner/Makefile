all: banana.html pb.html

%.html: %.xhtml
	-lore -n --output lint $<
	lore -p --config template=../../doc/core/howto/template.tpl \
		--config ext=.html $<

TEST=test_banana test_schema test_pb
test:
	../../bin/trial -v $(TEST)
test2:
	python -Wignore ../../bin/trial -o $(TEST)

clean:
	rm -f *~ *.pyc *.html
	rm -rf _trial_temp
