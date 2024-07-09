\if :{?actual}
select result(:'testname', :'expected', :'actual');
\else
select result(:'testname', :'expected', null);
\endif
\unset actual
