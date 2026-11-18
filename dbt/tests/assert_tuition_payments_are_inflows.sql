-- Returns rows if any tuition payment is linked to a financial transaction
-- whose cost center is not classified as a revenue inflow (flow_type = 'IN').
with tuition_payments as (

    select
        transaction_id,
        customer_id,
        reference_month
    from {{ ref('stg_kumon__tuition_payments') }}

),

financial_transactions as (

    select
        transaction_id,
        cost_center_id,
        amount
    from {{ ref('stg_kumon__financial_transactions') }}

),

cost_centers as (

    select
        cost_center_id,
        cost_center_name,
        flow_type
    from {{ ref('stg_kumon__cost_centers') }}

)

select
    tp.transaction_id,
    tp.customer_id,
    tp.reference_month,
    ft.cost_center_id,
    cc.cost_center_name,
    cc.flow_type
from tuition_payments as tp
inner join financial_transactions as ft
    on tp.transaction_id = ft.transaction_id
inner join cost_centers as cc
    on ft.cost_center_id = cc.cost_center_id
where cc.flow_type != 'IN'