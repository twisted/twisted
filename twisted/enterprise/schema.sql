DROP TABLE twisted_identities;
DROP TABLE twisted_services;
DROP TABLE twisted_perspectives;

CREATE TABLE twisted_identities
(
      identity_name     varchar(64) PRIMARY KEY,
      password          varchar(64)
);
    
CREATE TABLE twisted_services
(
      service_name      varchar(64) PRIMARY KEY
);
    
CREATE TABLE twisted_perspectives
(
      identity_name     varchar(64) NOT NULL,
      perspective_name  varchar(64) NOT NULL,
      service_name      varchar(64) NOT NULL,
      perspective_type  varchar(64)
);
