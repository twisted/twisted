

CREATE TABLE licenses (
	license_key varchar(64) PRIMARY KEY,
	license_secret varchar(64),
	license_type varchar(64),
	license_user varchar(64),
	license_email varchar(64),
	license_org varchar(64),
	license_dir varchar(64),
	license_host varchar(64)
	);
