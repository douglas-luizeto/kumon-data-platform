-- Returns rows if any financial transaction linked to a tuition invoice
-- is associated with a cost center that is not a revenue inflow (flow_type = 'IN').
with financial_transactions as (

    select
        transaction_id,
        invoice_id,
        cost_center_id,
        amount
    from {{ ref('stg_kumon__financial_transactions') }}
    where invoice_id is not null

),

cost_centers as (

    select
        cost_center_id,
        cost_center_name,
        flow_type
    from {{ ref('stg_kumon__cost_centers') }}

)

select
    ft.transaction_id,
    ft.invoice_id,
    ft.cost_center_id,
    cc.cost_center_name,
    cc.flow_type
from financial_transactions as ft
inner join cost_centers as cc
    on ft.cost_center_id = cc.cost_center_id
where cc.flow_type != 'IN'