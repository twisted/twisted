experimental forum code that uses a postgres database to store messages.

to create the required tables and some sample data run:

createdb twisted
psql twisted -f forum.sql
psql twisted -f populate.sql

to run a twisted forum server, from this directory:

twistd -n -t config.tac 

TODO:

      * create Message and Thread "business objects" that have database
        representations rather than doing everything in the web UI!
      * add authentication and account hookup
      * add account creation
      * fix sorting issues in display of messages
      * fix random postgres ROLLBACK error messages (!?)
      * show only a screenful of messages at a time and allow browsing forwards
        and back by screen
      * unit tests, unit tests, unit tests
