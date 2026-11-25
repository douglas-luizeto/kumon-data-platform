with source as (

    select * from {{ source('raw_postgres', 'tuition_invoice_items') }}

),

renamed as (

    select
        trim(invoice_item_id) as invoice_item_id,
        trim(invoice_id) as invoice_id,
        trim(account_id) as account_id,
        cast(amount as numeric) as amount

    from source

)

select * from renamed