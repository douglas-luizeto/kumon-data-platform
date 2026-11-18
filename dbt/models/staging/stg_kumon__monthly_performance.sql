with source as (

    select * from {{ source('raw_postgres', 'monthly_performance') }}

),

renamed as (

    select
        cast(performance_id as int64) as performance_id,
        trim(account_id) as account_id,
        cast(reference_month as date) as reference_month,
        cast(final_stage_id as int64) as final_stage_id,
        cast(final_lesson_number as int64) as final_lesson_number,
        cast(sheets_completed as int64) as sheets_completed,
        trim(status_id) as status_id

    from source

)

select * from renamed