-- Returns rows if a monthly performance snapshot references a final_stage_id
-- that belongs to a different subject than the account's enrolled subject_id.
with performance as (

    select
        performance_id,
        account_id,
        reference_month,
        final_stage_id
    from {{ ref('stg_kumon__monthly_performance') }}

),

accounts as (

    select
        account_id,
        subject_id as account_subject_id
    from {{ ref('stg_kumon__accounts') }}

),

stages as (

    select
        stage_id,
        subject_id as stage_subject_id,
        stage_name
    from {{ ref('stg_kumon__stages') }}

)

select
    p.performance_id,
    p.account_id,
    p.reference_month,
    a.account_subject_id,
    p.final_stage_id,
    s.stage_name,
    s.stage_subject_id
from performance as p
inner join accounts as a
    on p.account_id = a.account_id
inner join stages as s
    on p.final_stage_id = s.stage_id
where a.account_subject_id != s.stage_subject_id