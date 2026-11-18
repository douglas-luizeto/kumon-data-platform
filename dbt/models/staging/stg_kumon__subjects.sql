with source as (

    select * from {{ source('raw_postgres', 'subjects') }}

),

renamed as (

    select
        trim(subject_id) as subject_id,
        trim(subject_name) as subject_name

    from source

)

select * from renamed