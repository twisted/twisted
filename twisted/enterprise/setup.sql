/* setup the accounts database for twisted user authentication */
/* WARNING: this will drop and re-create the twisted database if it exists. */

use master
go

if exists (select * from master.dbo.sysdatabases where name = "twisted")
begin
    print "Database twisted exists. Dropping it."
    drop database twisted
end
go

sp_droplogin twisted
go

sp_addlogin twisted, matrix
go

create database twisted on default
go

use twisted
go

sp_changedbowner twisted
go

print 'Creating the accounts table'

CREATE TABLE accounts
(
    name        varchar(32) not null,
    passwd    varchar(32) not null,
    account_id   integer not null
)
go

execute sp_primarykey accounts, name
go

create unique clustered index nameind
on accounts (name)
go

