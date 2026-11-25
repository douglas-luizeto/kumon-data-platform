with source as (

    select * from {{ source('raw_postgres', 'customers') }}

),

renamed as (

    select
        trim(customer_id) as customer_id,
        trim(cpf) as cpf,
        trim(customer_name) as customer_name,
        trim(email) as email,
        trim(phone1) as phone1,
        trim(phone2) as phone2,
        trim(street) as street,
        trim(address_number) as address_number,
        trim(complement) as complement,
        trim(district) as district,
        trim(zip_code) as zip_code,
        trim(city) as city,
        trim(state) as state,
        trim(country) as country,
        cast(due_day as int64) as due_day,
        cast(default_payment_method_id as int64) as default_payment_method_id

    from source

)

select * from renamed