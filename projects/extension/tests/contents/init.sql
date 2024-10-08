
drop database if exists toc with (force);
create database toc;
\c toc

create extension ai cascade;

-- display the contents of the extension
\dx+ ai

-- verbose display of the objects in the ai schema
\d+ ai.*
