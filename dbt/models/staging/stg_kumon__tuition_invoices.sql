with source as (

    select * from {{ source('raw_postgres', 'tuition_invoices') }}

),

renamed as (

    select
        trim(invoice_id) as invoice_id,
        trim(customer_id) as customer_id,
        cast(competence_date as date) as competence_date,
        cast(due_date as date) as due_date,
        cast(total_amount as numeric) as total_amount

    from source

)

select * from renamed