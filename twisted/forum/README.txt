experimental forum code that uses a postgres database to store messages.

to create the required tables and some sample data run:

psql -f forum.sql
psql -f populate.sql


to run a twisted forum server, from this directory:

twistd -n -t config.tac 


TODO:
	add authentication and account hookup
	add account creation
	fix sorting issues in display of messages
	fix random postgres ROLLBACK error messages (!?)
	show only a screenful of messages at a time and allow browsing forwards and back by screen
	unit tests, unit tests, unit tests
