all: lint banana.xhtml

lint: banana.html
	-lore -n --output lint $<
banana.xhtml: banana.html
	lore -p --config template=../../doc/howto/template.tpl $<
