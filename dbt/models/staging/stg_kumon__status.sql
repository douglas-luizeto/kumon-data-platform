with source as (

    select * from {{ source('raw_postgres', 'status') }}

),

renamed as (

    select
        trim(status_id) as status_id,
        trim(status_name) as status_name,
        trim(description) as description

    from source

)

select * from renamed