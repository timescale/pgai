from pathlib import Path

import psycopg
from psycopg.sql import SQL, Identifier

import pgai
from tests.semantic_catalog.utils import (
    PostgresContainer,
)


async def test_desc_injest(container: PostgresContainer):
    database = "test_desc_injest"
    container.drop_database(database)
    container.create_database(database)
    expected: set[str] = {
        "postgres_air.account",
        "postgres_air.account.account_id",
        "postgres_air.account.login",
        "postgres_air.account.first_name",
        "postgres_air.account.last_name",
        "postgres_air.account.frequent_flyer_id",
        "postgres_air.account.update_ts",
        "postgres_air.aircraft",
        "postgres_air.aircraft.model",
        "postgres_air.aircraft.range",
        "postgres_air.aircraft.class",
        "postgres_air.aircraft.velocity",
        "postgres_air.aircraft.code",
        "postgres_air.airport",
        "postgres_air.airport.airport_code",
        "postgres_air.airport.airport_name",
        "postgres_air.airport.city",
        "postgres_air.airport.airport_tz",
        "postgres_air.airport.continent",
        "postgres_air.airport.iso_country",
        "postgres_air.airport.iso_region",
        "postgres_air.airport.intnl",
        "postgres_air.airport.update_ts",
        "postgres_air.boarding_pass",
        "postgres_air.boarding_pass.pass_id",
        "postgres_air.boarding_pass.passenger_id",
        "postgres_air.boarding_pass.booking_leg_id",
        "postgres_air.boarding_pass.seat",
        "postgres_air.boarding_pass.boarding_time",
        "postgres_air.boarding_pass.precheck",
        "postgres_air.boarding_pass.update_ts",
        "postgres_air.booking",
        "postgres_air.booking.booking_id",
        "postgres_air.booking.booking_ref",
        "postgres_air.booking.booking_name",
        "postgres_air.booking.account_id",
        "postgres_air.booking.email",
        "postgres_air.booking.phone",
        "postgres_air.booking.update_ts",
        "postgres_air.booking.price",
        "postgres_air.booking_leg",
        "postgres_air.booking_leg.booking_leg_id",
        "postgres_air.booking_leg.booking_id",
        "postgres_air.booking_leg.flight_id",
        "postgres_air.booking_leg.leg_num",
        "postgres_air.booking_leg.is_returning",
        "postgres_air.booking_leg.update_ts",
        "postgres_air.events",
        "postgres_air.events.time",
        "postgres_air.events.name",
        "postgres_air.events.params",
        "postgres_air.flight",
        "postgres_air.flight.flight_id",
        "postgres_air.flight.flight_no",
        "postgres_air.flight.scheduled_departure",
        "postgres_air.flight.scheduled_arrival",
        "postgres_air.flight.departure_airport",
        "postgres_air.flight.arrival_airport",
        "postgres_air.flight.status",
        "postgres_air.flight.aircraft_code",
        "postgres_air.flight.actual_departure",
        "postgres_air.flight.actual_arrival",
        "postgres_air.flight.update_ts",
        "postgres_air.frequent_flyer",
        "postgres_air.frequent_flyer.frequent_flyer_id",
        "postgres_air.frequent_flyer.first_name",
        "postgres_air.frequent_flyer.last_name",
        "postgres_air.frequent_flyer.title",
        "postgres_air.frequent_flyer.card_num",
        "postgres_air.frequent_flyer.level",
        "postgres_air.frequent_flyer.award_points",
        "postgres_air.frequent_flyer.email",
        "postgres_air.frequent_flyer.phone",
        "postgres_air.frequent_flyer.update_ts",
        "postgres_air.hypertable_test",
        "postgres_air.hypertable_test.time",
        "postgres_air.hypertable_test.location",
        "postgres_air.hypertable_test.time_received",
        "postgres_air.hypertable_test.params",
        "postgres_air.passenger",
        "postgres_air.passenger.passenger_id",
        "postgres_air.passenger.booking_id",
        "postgres_air.passenger.booking_ref",
        "postgres_air.passenger.passenger_no",
        "postgres_air.passenger.first_name",
        "postgres_air.passenger.last_name",
        "postgres_air.passenger.account_id",
        "postgres_air.passenger.update_ts",
        "postgres_air.passenger.age",
        "postgres_air.phone",
        "postgres_air.phone.phone_id",
        "postgres_air.phone.account_id",
        "postgres_air.phone.phone",
        "postgres_air.phone.phone_type",
        "postgres_air.phone.primary_phone",
        "postgres_air.phone.update_ts",
        "postgres_air.events_daily",
        "postgres_air.events_daily.name",
        "postgres_air.events_daily.bucket",
        "postgres_air.flight_summary",
        "postgres_air.flight_summary.flight_no",
        "postgres_air.flight_summary.departure_airport",
        "postgres_air.flight_summary.arrival_airport",
        "postgres_air.flight_summary.scheduled_departure",
        "postgres_air.passenger_details",
        "postgres_air.passenger_details.first_name",
        "postgres_air.passenger_details.last_name",
        "postgres_air.passenger_details.booking_ref",
        "postgres_air.advance_air_time",
        "postgres_air.update_flight_status",
    }
    script = Path(__file__).parent.joinpath("data", "descriptions.sql").read_text()
    connection_str = container.connection_string(database=database)
    pgai.install(connection_str)
    async with await psycopg.AsyncConnection.connect(connection_str) as con:  # noqa SIM117
        async with con.cursor() as cur:
            await cur.execute("select ai.create_semantic_catalog('my_catalog')")
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to create catalog")
            catalog_id: int = int(row[0])
            await con.commit()
            for line in script.split("\n"):
                await cur.execute(line)  # pyright: ignore [reportArgumentType]
                await con.commit()
            query = SQL("""\
                select array_to_string(x.objnames, '.')
                from ai.{} x
                where x.description is not null
            """).format(Identifier(f"semantic_catalog_obj_{catalog_id}"))
            await cur.execute(query)
            actual: set[str] = set()
            async for row in cur:
                actual.add(row[0])
    assert actual == expected
