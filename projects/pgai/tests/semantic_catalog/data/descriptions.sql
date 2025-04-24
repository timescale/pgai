-- objects
select ai.sc_set_table_desc(1259, 66548, 'postgres_air', 'airport', 'A table that stores information about airports including their codes, names, locations, and international status.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 1, 'postgres_air', 'airport', 'airport_code', 'A three-character unique identifier code for the airport that serves as the primary key.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 2, 'postgres_air', 'airport', 'airport_name', 'The full name of the airport.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 3, 'postgres_air', 'airport', 'city', 'The city where the airport is located.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 4, 'postgres_air', 'airport', 'airport_tz', 'The time zone in which the airport operates.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 5, 'postgres_air', 'airport', 'continent', 'The continent where the airport is located.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 6, 'postgres_air', 'airport', 'iso_country', 'The ISO code of the country where the airport is located.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 7, 'postgres_air', 'airport', 'iso_region', 'The ISO code of the region or state where the airport is located.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 8, 'postgres_air', 'airport', 'intnl', 'A boolean value indicating whether the airport handles international flights.', 'default');
select ai.sc_set_table_col_desc(1259, 66548, 9, 'postgres_air', 'airport', 'update_ts', 'The timestamp when the airport record was last updated, including timezone information.', 'default');
select ai.sc_set_view_desc(1259, 66687, 'postgres_air', 'flight_summary', 'A summary view of PostgreSQL Air flights showing flight numbers, departure and arrival airports, and scheduled departure times.', 'default');
select ai.sc_set_view_col_desc(1259, 66687, 1, 'postgres_air', 'flight_summary', 'flight_no', 'The unique identifier or code for each flight.', 'default');
select ai.sc_set_view_col_desc(1259, 66687, 2, 'postgres_air', 'flight_summary', 'departure_airport', 'The three-character code representing the airport where the flight departs from.', 'default');
select ai.sc_set_view_col_desc(1259, 66687, 3, 'postgres_air', 'flight_summary', 'arrival_airport', 'The three-character code representing the airport where the flight arrives at.', 'default');
select ai.sc_set_view_col_desc(1259, 66687, 4, 'postgres_air', 'flight_summary', 'scheduled_departure', 'The date and time when the flight is scheduled to depart, with timezone information.', 'default');
select ai.sc_set_proc_desc(1255, 66536, 'postgres_air', 'advance_air_time', '{integer,pg_catalog.text,boolean}', 'Advances all timestamp and timestamptz fields in a specified schema by a configurable number of weeks with options to preview or execute updates.', 'default');

-- sql examples
select ai.sc_add_sql_desc($$select * from postgres_air.flight f where f.status = 'Delayed'$$, 'Delayed flights are indicated by their status', 'default');

-- facts
select ai.sc_add_fact('The postgres_air.airport.iso_region values are in uppercase.', 'default');
select ai.sc_add_fact('The postgres_air.airport.airport_code values are in uppercase.', 'default');
