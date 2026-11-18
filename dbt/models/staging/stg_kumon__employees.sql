with source as (

    select * from {{ source('raw_postgres', 'employees') }}

),

renamed as (

    select
        trim(emp_id) as emp_id,
        trim(emp_name) as emp_name,
        trim(employee_type) as employee_type,
        cast(teaches_m as bool) as teaches_m,
        cast(teaches_p as bool) as teaches_p,
        cast(teaches_i as bool) as teaches_i,
        cast(teaches_j as bool) as teaches_j,
        trim(phone1) as phone1,
        trim(phone2) as phone2,
        trim(email) as email,
        cast(salary as numeric) as salary,
        cast(contract_start as date) as contract_start,
        cast(contract_end as date) as contract_end,
        contract_end is null as is_active

    from source

)

select * from renamed