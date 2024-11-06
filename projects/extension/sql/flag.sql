do $feature_flag$ /*{feature_flag}*/
begin
    if (select coalesce(pg_catalog.current_setting('{guc}', true), 'false') = 'true') then
        raise warning '%', pg_catalog.concat_ws
        ( ' '
        , 'Feature flag "{feature_flag}" has been enabled.'
        , 'Pre-release software will be installed.'
        , 'This code is not production-grade, is not guaranteed to work, and is not supported in any way.'
        , 'Extension upgrades are not supported once pre-release software has been installed.'
        );

        insert into ai.feature_flag ("name", applied_at_version)
        values ('{feature_flag}', '{version}')
        on conflict on constraint feature_flag_pkey
        do nothing
        ;
    end if;
end
$feature_flag$;

