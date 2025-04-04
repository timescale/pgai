/*
BSD 3-Clause License

Copyright (c) 2020, hettie-d
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4 (Debian 17.4-1.pgdg120+2)
-- Dumped by pg_dump version 17.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgres_air; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA postgres_air;


--
-- Name: advance_air_time(integer, text, boolean); Type: PROCEDURE; Schema: postgres_air; Owner: -
--

CREATE PROCEDURE postgres_air.advance_air_time(IN p_weeks integer DEFAULT 52, IN p_schema_name text DEFAULT 'postgres_air'::text, IN p_run boolean DEFAULT false)
    LANGUAGE plpgsql
    AS $_$
declare   stmt text;
begin
raise notice $$Interval: % $$,  make_interval (weeks=>p_weeks);
if p_run 
then raise notice $$Executing updates$$;
else raise notice $$Displaying only$$;
   end if;
----
for stmt in
   select 
      ---  nspname, relname, attname, typname
   'update  '||nspname ||'.'|| relname ||' set '
   || string_agg(attname || '='|| attname
      ||'+make_interval(weeks=>' || p_weeks ||')', ',') 
   ||';'
from pg_class r
join pg_attribute a on a.attrelid=r.oid
join pg_type t on t.oid=a.atttypid
join  pg_namespace n on relnamespace = n.oid
where relkind='r'
   and attnum>0
   and n.nspname  = p_schema_name
   and typname  in ('timestamptz','timestamp')
group  by  nspname, relname
order by  nspname, relname
loop
   raise notice $$ - % $$, stmt;
   if p_run 
   then execute stmt;
      end if;
   end loop;
end;
$_$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.account (
    account_id integer NOT NULL,
    login text NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    frequent_flyer_id integer,
    update_ts timestamp with time zone
);


--
-- Name: account_account_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.account_account_id_seq
    AS integer
    START WITH 300001
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_account_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.account_account_id_seq OWNED BY postgres_air.account.account_id;


--
-- Name: aircraft; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.aircraft (
    model text,
    range numeric NOT NULL,
    class integer NOT NULL,
    velocity numeric NOT NULL,
    code text NOT NULL
);


--
-- Name: airport; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.airport (
    airport_code character(3) NOT NULL,
    airport_name text NOT NULL,
    city text NOT NULL,
    airport_tz text NOT NULL,
    continent text,
    iso_country text,
    iso_region text,
    intnl boolean NOT NULL,
    update_ts timestamp with time zone
);


--
-- Name: boarding_pass_pass_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.boarding_pass_pass_id_seq
    START WITH 25293500
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: boarding_pass; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.boarding_pass (
    pass_id integer DEFAULT nextval('postgres_air.boarding_pass_pass_id_seq'::regclass) NOT NULL,
    passenger_id bigint,
    booking_leg_id bigint,
    seat text,
    boarding_time timestamp with time zone,
    precheck boolean,
    update_ts timestamp with time zone
);


--
-- Name: booking; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.booking (
    booking_id bigint NOT NULL,
    booking_ref text NOT NULL,
    booking_name text,
    account_id integer,
    email text NOT NULL,
    phone text NOT NULL,
    update_ts timestamp with time zone,
    price numeric(7,2)
);


--
-- Name: booking_leg; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.booking_leg (
    booking_leg_id integer NOT NULL,
    booking_id integer NOT NULL,
    flight_id integer NOT NULL,
    leg_num integer,
    is_returning boolean,
    update_ts timestamp with time zone
);


--
-- Name: booking_leg_booking_leg_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.booking_leg_booking_leg_id_seq
    AS integer
    START WITH 17893600
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_leg_booking_leg_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.booking_leg_booking_leg_id_seq OWNED BY postgres_air.booking_leg.booking_leg_id;


--
-- Name: booking_number; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.booking_number
    START WITH 5743216
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: flight; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.flight (
    flight_id integer NOT NULL,
    flight_no text NOT NULL,
    scheduled_departure timestamp with time zone NOT NULL,
    scheduled_arrival timestamp with time zone NOT NULL,
    departure_airport character(3) NOT NULL,
    arrival_airport character(3) NOT NULL,
    status text NOT NULL,
    aircraft_code character(3) NOT NULL,
    actual_departure timestamp with time zone,
    actual_arrival timestamp with time zone,
    update_ts timestamp with time zone
);


--
-- Name: flight_flight_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.flight_flight_id_seq
    AS integer
    START WITH 683180
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: flight_flight_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.flight_flight_id_seq OWNED BY postgres_air.flight.flight_id;


--
-- Name: frequent_flyer; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.frequent_flyer (
    frequent_flyer_id integer NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    title text NOT NULL,
    card_num text NOT NULL,
    level integer NOT NULL,
    award_points integer NOT NULL,
    email text NOT NULL,
    phone text NOT NULL,
    update_ts timestamp with time zone
);


--
-- Name: frequent_flyer_frequent_flyer_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.frequent_flyer_frequent_flyer_id_seq
    AS integer
    START WITH 128356
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: frequent_flyer_frequent_flyer_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.frequent_flyer_frequent_flyer_id_seq OWNED BY postgres_air.frequent_flyer.frequent_flyer_id;


--
-- Name: passenger; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.passenger (
    passenger_id integer NOT NULL,
    booking_id integer NOT NULL,
    booking_ref text,
    passenger_no integer,
    first_name text NOT NULL,
    last_name text NOT NULL,
    account_id integer,
    update_ts timestamp with time zone,
    age integer
);


--
-- Name: passenger_passenger_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.passenger_passenger_id_seq
    AS integer
    START WITH 16313699
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: passenger_passenger_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.passenger_passenger_id_seq OWNED BY postgres_air.passenger.passenger_id;


--
-- Name: phone; Type: TABLE; Schema: postgres_air; Owner: -
--

CREATE TABLE postgres_air.phone (
    phone_id integer NOT NULL,
    account_id integer,
    phone text,
    phone_type text,
    primary_phone boolean,
    update_ts timestamp with time zone
);


--
-- Name: phone_phone_id_seq; Type: SEQUENCE; Schema: postgres_air; Owner: -
--

CREATE SEQUENCE postgres_air.phone_phone_id_seq
    AS integer
    START WITH 407449
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: phone_phone_id_seq; Type: SEQUENCE OWNED BY; Schema: postgres_air; Owner: -
--

ALTER SEQUENCE postgres_air.phone_phone_id_seq OWNED BY postgres_air.phone.phone_id;


--
-- Name: account account_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.account ALTER COLUMN account_id SET DEFAULT nextval('postgres_air.account_account_id_seq'::regclass);


--
-- Name: booking_leg booking_leg_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking_leg ALTER COLUMN booking_leg_id SET DEFAULT nextval('postgres_air.booking_leg_booking_leg_id_seq'::regclass);


--
-- Name: flight flight_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.flight ALTER COLUMN flight_id SET DEFAULT nextval('postgres_air.flight_flight_id_seq'::regclass);


--
-- Name: frequent_flyer frequent_flyer_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.frequent_flyer ALTER COLUMN frequent_flyer_id SET DEFAULT nextval('postgres_air.frequent_flyer_frequent_flyer_id_seq'::regclass);


--
-- Name: passenger passenger_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.passenger ALTER COLUMN passenger_id SET DEFAULT nextval('postgres_air.passenger_passenger_id_seq'::regclass);


--
-- Name: phone phone_id; Type: DEFAULT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.phone ALTER COLUMN phone_id SET DEFAULT nextval('postgres_air.phone_phone_id_seq'::regclass);


--
-- Name: account account_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (account_id);


--
-- Name: aircraft aircraft_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.aircraft
    ADD CONSTRAINT aircraft_pkey PRIMARY KEY (code);


--
-- Name: airport airport_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.airport
    ADD CONSTRAINT airport_pkey PRIMARY KEY (airport_code);


--
-- Name: boarding_pass boarding_pass_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.boarding_pass
    ADD CONSTRAINT boarding_pass_pkey PRIMARY KEY (pass_id);


--
-- Name: booking booking_booking_ref_key; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking
    ADD CONSTRAINT booking_booking_ref_key UNIQUE (booking_ref);


--
-- Name: booking_leg booking_leg_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking_leg
    ADD CONSTRAINT booking_leg_pkey PRIMARY KEY (booking_leg_id);


--
-- Name: booking booking_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking
    ADD CONSTRAINT booking_pkey PRIMARY KEY (booking_id);


--
-- Name: flight flight_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.flight
    ADD CONSTRAINT flight_pkey PRIMARY KEY (flight_id);


--
-- Name: frequent_flyer frequent_flyer_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.frequent_flyer
    ADD CONSTRAINT frequent_flyer_pkey PRIMARY KEY (frequent_flyer_id);


--
-- Name: passenger passenger_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.passenger
    ADD CONSTRAINT passenger_pkey PRIMARY KEY (passenger_id);


--
-- Name: phone phone_pkey; Type: CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.phone
    ADD CONSTRAINT phone_pkey PRIMARY KEY (phone_id);


--
-- Name: flight aircraft_code_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.flight
    ADD CONSTRAINT aircraft_code_fk FOREIGN KEY (aircraft_code) REFERENCES postgres_air.aircraft(code);


--
-- Name: flight arrival_airport_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.flight
    ADD CONSTRAINT arrival_airport_fk FOREIGN KEY (arrival_airport) REFERENCES postgres_air.airport(airport_code);


--
-- Name: booking booking_account_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking
    ADD CONSTRAINT booking_account_id_fk FOREIGN KEY (account_id) REFERENCES postgres_air.account(account_id);


--
-- Name: booking_leg booking_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking_leg
    ADD CONSTRAINT booking_id_fk FOREIGN KEY (booking_id) REFERENCES postgres_air.booking(booking_id);


--
-- Name: boarding_pass booking_leg_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.boarding_pass
    ADD CONSTRAINT booking_leg_id_fk FOREIGN KEY (booking_leg_id) REFERENCES postgres_air.booking_leg(booking_leg_id);


--
-- Name: flight departure_airport_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.flight
    ADD CONSTRAINT departure_airport_fk FOREIGN KEY (departure_airport) REFERENCES postgres_air.airport(airport_code);


--
-- Name: booking_leg flight_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.booking_leg
    ADD CONSTRAINT flight_id_fk FOREIGN KEY (flight_id) REFERENCES postgres_air.flight(flight_id);


--
-- Name: account frequent_flyer_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.account
    ADD CONSTRAINT frequent_flyer_id_fk FOREIGN KEY (frequent_flyer_id) REFERENCES postgres_air.frequent_flyer(frequent_flyer_id);


--
-- Name: passenger pass_account_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.passenger
    ADD CONSTRAINT pass_account_id_fk FOREIGN KEY (account_id) REFERENCES postgres_air.account(account_id);


--
-- Name: passenger pass_booking_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.passenger
    ADD CONSTRAINT pass_booking_id_fk FOREIGN KEY (booking_id) REFERENCES postgres_air.booking(booking_id);


--
-- Name: passenger pass_frequent_flyer_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.passenger
    ADD CONSTRAINT pass_frequent_flyer_id_fk FOREIGN KEY (account_id) REFERENCES postgres_air.account(account_id);


--
-- Name: boarding_pass passenger_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.boarding_pass
    ADD CONSTRAINT passenger_id_fk FOREIGN KEY (passenger_id) REFERENCES postgres_air.passenger(passenger_id);


--
-- Name: phone phone_account_id_fk; Type: FK CONSTRAINT; Schema: postgres_air; Owner: -
--

ALTER TABLE ONLY postgres_air.phone
    ADD CONSTRAINT phone_account_id_fk FOREIGN KEY (account_id) REFERENCES postgres_air.account(account_id);


--
-- PostgreSQL database dump complete
--

