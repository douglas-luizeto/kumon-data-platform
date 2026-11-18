with source as (

    select * from {{ source('raw_postgres', 'tuition_payments') }}

),

renamed as (

    select
        trim(transaction_id) as transaction_id,
        trim(customer_id) as customer_id,
        cast(reference_month as date) as reference_month,
        cast(due_date as date) as due_date

    from source

)

select * from renamed