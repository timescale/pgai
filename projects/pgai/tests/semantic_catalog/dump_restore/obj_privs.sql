select
  x.objtype
, x.objnames[1] as "schema"
, x.objnames[2] as "object"
, case
    when x.objtype in ('table', 'view') then
        has_table_privilege('bot', x.objid, 'select')
    else
        has_function_privilege('bot', x.objid, 'execute')
  end as has_access
from ai.semantic_catalog_obj_1 x
where x.objsubid = 0
order by x.objtype, x.objnames
;