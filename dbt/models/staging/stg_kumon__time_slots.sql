with source as (

    select * from {{ source('raw_postgres', 'time_slots') }}

),

renamed as (

    select
        cast(time_slot_id as int64) as time_slot_id,
        cast(day_of_week as int64) as day_of_week,
        slot_time,
        cast(max_capacity as int64) as max_capacity

    from source

)

select * from renamed