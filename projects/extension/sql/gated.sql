-------------------------------------------------------------------------------
-- {feature_flag}
do $gated_by_feature_flag$
begin
if (select coalesce(pg_catalog.current_setting('{guc}', true), 'false') != 'true') then
    return;
end if;
{code}
end;
$gated_by_feature_flag$;
