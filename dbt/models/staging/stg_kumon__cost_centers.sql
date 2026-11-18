with source as (

    select * from {{ source('raw_postgres', 'cost_centers') }}

),

renamed as (

    select
        cast(cost_center_id as int64) as cost_center_id,
        trim(cost_center_name) as cost_center_name,
        trim(flow_type) as flow_type,
        trim(flow_type) = 'IN' as is_inflow,
        trim(cost_nature) as cost_nature,
        trim(description) as description

    from source

)

select * from renamed