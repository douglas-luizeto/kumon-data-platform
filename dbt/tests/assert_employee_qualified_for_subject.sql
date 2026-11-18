-- Returns rows if an employee assigned to an account (employee_1_id or employee_2_id)
-- is not qualified to teach that account's subject_id.
with accounts as (

    select
        account_id,
        subject_id,
        employee_1_id,
        employee_2_id
    from {{ ref('stg_kumon__accounts') }}

),

employees as (

    select
        emp_id,
        emp_name,
        teaches_m,
        teaches_p,
        teaches_i,
        teaches_j
    from {{ ref('stg_kumon__employees') }}

),

assigned_employees as (

    select
        account_id,
        subject_id,
        employee_1_id as emp_id,
        'employee_1' as assignment_role
    from accounts
    where employee_1_id is not null

    union all

    select
        account_id,
        subject_id,
        employee_2_id as emp_id,
        'employee_2' as assignment_role
    from accounts
    where employee_2_id is not null

)

select
    ae.account_id,
    ae.subject_id,
    ae.assignment_role,
    e.emp_id,
    e.emp_name,
    e.teaches_m,
    e.teaches_p,
    e.teaches_i,
    e.teaches_j
from assigned_employees as ae
inner join employees as e
    on ae.emp_id = e.emp_id
where
    (ae.subject_id = 'm' and not e.teaches_m)
    or (ae.subject_id = 'p' and not e.teaches_p)
    or (ae.subject_id = 'i' and not e.teaches_i)
    or (ae.subject_id = 'j' and not e.teaches_j)