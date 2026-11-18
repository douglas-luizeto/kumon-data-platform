-- Returns rows if any interaction is scheduled prior to the account's enrollment date.
with interactions as (

    select
        interaction_id,
        account_id,
        expected_date
    from {{ ref('stg_kumon__interactions') }}

),

accounts as (

    select
        account_id,
        enroll_date
    from {{ ref('stg_kumon__accounts') }}

)

select
    i.interaction_id,
    i.account_id,
    a.enroll_date,
    i.expected_date
from interactions as i
inner join accounts as a
    on i.account_id = a.account_id
where i.expected_date < a.enroll_date