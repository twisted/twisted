experimental forum code that uses a postgres database to store messages.

to create the required tables and some sample data run:

createdb twisted
psql twisted -f forum.sql
psql twisted -f populate.sql

to run a twisted forum server, from this directory:

twistd -n -t config.tac 

TODO:
      * add authentication and account hookup
      * add account creation
      * guest user access
      * moderators and moderating
      * forum level persmissions
      * fix sorting issues in display of messages
      * show only a screenful of messages at a time and allow browsing forwards
        and back by screen
      * unit tests, unit tests, unit tests
