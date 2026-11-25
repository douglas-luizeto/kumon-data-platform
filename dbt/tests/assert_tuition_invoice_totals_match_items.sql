-- Returns rows if any tuition invoice header total_amount does not match
-- the sum of its corresponding line items in tuition_invoice_items.
with invoices as (

    select
        invoice_id,
        total_amount
    from {{ ref('stg_kumon__tuition_invoices') }}

),

items_agg as (

    select
        invoice_id,
        sum(amount) as sum_items_amount
    from {{ ref('stg_kumon__tuition_invoice_items') }}
    group by 1

)

select
    inv.invoice_id,
    inv.total_amount,
    coalesce(ia.sum_items_amount, 0) as sum_items_amount
from invoices as inv
left join items_agg as ia
    on inv.invoice_id = ia.invoice_id
where inv.total_amount != coalesce(ia.sum_items_amount, 0)