with source as (

    select * from {{ source('raw_postgres', 'accounts') }}

),

renamed as (

    select
        trim(account_id) as account_id,
        cast(kumon_id as int64) as kumon_id,
        trim(account_name) as account_name,
        cast(birth_date as date) as birth_date,
        trim(gender) as gender,
        trim(customer_id) as customer_id,
        trim(subject_id) as subject_id,
        cast(initial_stage_id as int64) as initial_stage_id,
        cast(enroll_date as date) as enroll_date,
        cast(cancellation_date as date) as cancellation_date,
        cancellation_date is not null as is_canceled,
        trim(declared_churn_reason) as declared_churn_reason,
        trim(modality) as modality,
        trim(study_medium) as study_medium,
        cast(time_slot_1 as int64) as time_slot_1_id,
        trim(emp_1) as employee_1_id,
        cast(time_slot_2 as int64) as time_slot_2_id,
        trim(emp_2) as employee_2_id,
        cast(monthly_fee as numeric) as monthly_fee,
        cast(due_day as int64) as due_day,
        cast(default_payment_method_id as int64) as default_payment_method_id

    from source

)

select * from renamed