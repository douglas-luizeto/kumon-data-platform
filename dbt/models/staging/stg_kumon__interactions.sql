with source as (

    select * from {{ source('raw_postgres', 'interactions') }}

),

renamed as (

    select
        trim(interaction_id) as interaction_id,
        trim(account_id) as account_id,
        cast(expected_date as date) as expected_date,
        cast(expected_time_slot_id as int64) as expected_time_slot_id,
        trim(rescheduled_from_id) as rescheduled_from_id,
        rescheduled_from_id is not null as is_rescheduled,
        cast(is_justified_absence as bool) as is_justified_absence,
        cast(start_ts as timestamp) as start_ts,
        cast(end_ts as timestamp) as end_ts,
        start_ts is not null as is_present,
        cast(days_studied_since_last as int64) as days_studied_since_last,
        cast(did_corrections as bool) as did_corrections,
        trim(study_quality) as study_quality,
        array(
            select trim(tag)
            from unnest(behavior_tags) as tag
        ) as behavior_tags

    from source

)

select * from renamed