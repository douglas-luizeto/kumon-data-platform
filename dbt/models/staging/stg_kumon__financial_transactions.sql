with source as (

    select * from {{ source('raw_postgres', 'financial_transactions') }}

),

renamed as (

    select
        trim(transaction_id) as transaction_id,
        cast(cost_center_id as int64) as cost_center_id,
        cast(payment_method_id as int64) as payment_method_id,
        cast(competence_date as date) as competence_date,
        trim(invoice_id) as invoice_id,
        cast(transaction_date as date) as transaction_date,
        cast(amount as numeric) as amount,
        trim(description) as description

    from source

)

select * from renamed