with source as (

    select * from {{ source('raw_postgres', 'payment_methods') }}

),

renamed as (

    select
        cast(payment_method_id as int64) as payment_method_id,
        trim(method_name) as method_name,
        cast(settlement_days as int64) as settlement_days,
        cast(fee_fixed as numeric) as fee_fixed,
        cast(fee_pct as numeric) as fee_pct

    from source

)

select * from renamed