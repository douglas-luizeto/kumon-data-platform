with source as (

    select * from {{ source('raw_postgres', 'stages') }}

),

renamed as (

    select
        cast(stage_id as int64) as stage_id,
        trim(subject_id) as subject_id,
        trim(stage_name) as stage_name,
        cast(stage_order as int64) as stage_order

    from source

)

select * from renamed