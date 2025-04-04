
create or replace view postgres_air.flight_summary as
select flight_no, departure_airport, arrival_airport, scheduled_departure
from postgres_air.flight;

create or replace view postgres_air.passenger_details as
select p.first_name, p.last_name, b.booking_ref
from postgres_air.passenger p
join postgres_air.booking b on p.booking_id = b.booking_id;

create or replace procedure postgres_air.update_flight_status
( flight_id integer
, status text
) language plpgsql as
$proc$
begin
    update postgres_air.flight
    set status = update_flight_status.status
    where flight_id = update_flight_status.flight_id;
end;
$proc$;
