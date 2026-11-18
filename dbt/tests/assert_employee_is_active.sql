-- Returns rows if an assigned employee (employee_1_id or employee_2_id) has a contract
-- that ended prior to an interaction's expected_date (or started after expected_date).
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
        employee_1_id,
        employee_2_id
    from {{ ref('stg_kumon__accounts') }}

),

employees as (

    select
        emp_id,
        emp_name,
        contract_start,
        contract_end
    from {{ ref('stg_kumon__employees') }}

),

account_employees as (

    select
        account_id,
        employee_1_id as emp_id,
        'employee_1' as assignment_role
    from accounts
    where employee_1_id is not null

    union all

    select
        account_id,
        employee_2_id as emp_id,
        'employee_2' as assignment_role
    from accounts
    where employee_2_id is not null

)

select
    i.interaction_id,
    i.account_id,
    i.expected_date,
    ae.assignment_role,
    e.emp_id,
    e.emp_name,
    e.contract_start,
    e.contract_end
from interactions as i
inner join account_employees as ae
    on i.account_id = ae.account_id
inner join employees as e
    on ae.emp_id = e.emp_id
where
    i.expected_date < e.contract_start
    or (e.contract_end is not null and i.expected_date > e.contract_end)