CREATE TABLE metrics_perspectives
(
      identity_name  varchar(64),
      hostname       varchar(64),
      server_group   varchar(64),    
      server_type    integer
);
    
CREATE TABLE metrics_items
(
      source_name    varchar(62),
      item_name      varchar(32),
      item_value     integer,
      collected      timestamp
);
    
CREATE TABLE metrics_events
(
      source_name    varchar(64),
      event_name     varchar(32),
      event_time     timestamp
);

CREATE TABLE metrics_variables
(
      variable_name  varchar(32),
      threshold      integer
);
