# Copyright (c) 2013, 	9t9it and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import formatdate, flt, add_days
from toolz import merge


def execute(filters=None):
    filters.day_before_from_date = add_days(filters.from_date, -1)
    columns, data = _get_columns(filters), _get_data(filters)
    return columns, data


def _get_columns(filters):
    return [
        {
            "label": _("DocType"),
            "fieldname": "doctype",
            "fieldtype": "Data",
            "options": "DocType",
            "width": 120,
        },
        {
            "label": _("Asset"),
            "fieldname": "name",
            "fieldtype": "Dynamic Link",
            "options": "doctype",
            "width": 120,
        },
        {
            "label": _("Asset Name"),
            "fieldname": "asset_name",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Cost as on") + " " + formatdate(filters.day_before_from_date),
            "fieldname": "cost_as_on_from_date",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Cost of New Purchase"),
            "fieldname": "cost_of_new_purchase",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Cost of Sold Asset"),
            "fieldname": "cost_of_sold_asset",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Cost of Scrapped Asset"),
            "fieldname": "cost_of_scrapped_asset",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Cost as on") + " " + formatdate(filters.to_date),
            "fieldname": "cost_as_on_to_date",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Accumulated Depreciation as on")
            + " "
            + formatdate(filters.day_before_from_date),
            "fieldname": "accumulated_depreciation_as_on_from_date",
            "fieldtype": "Currency",
            "width": 270,
        },
        {
            "label": _("Depreciation Amount during the period"),
            "fieldname": "depreciation_amount_during_the_period",
            "fieldtype": "Currency",
            "width": 240,
        },
        {
            "label": _("Depreciation Eliminated due to disposal of assets"),
            "fieldname": "depreciation_eliminated_during_the_period",
            "fieldtype": "Currency",
            "width": 300,
        },
        {
            "label": _("Accumulated Depreciation as on")
            + " "
            + formatdate(filters.to_date),
            "fieldname": "accumulated_depreciation_as_on_to_date",
            "fieldtype": "Currency",
            "width": 270,
        },
        {
            "label": _("Net Asset value as on")
            + " "
            + formatdate(filters.day_before_from_date),
            "fieldname": "net_asset_value_as_on_from_date",
            "fieldtype": "Currency",
            "width": 200,
        },
        {
            "label": _("Net Asset value as on") + " " + formatdate(filters.to_date),
            "fieldname": "net_asset_value_as_on_to_date",
            "fieldtype": "Currency",
            "width": 200,
        },
    ]


def _get_data(filters):
    data = []
    assets = _get_assets(filters)
    asset_costs = _get_asset_costs(filters)
    for asset_cost in asset_costs:
        row = frappe._dict(asset_cost)

        row.cost_as_on_to_date = (
            flt(row.cost_as_on_from_date)
            + flt(row.cost_of_new_purchase)
            - flt(row.cost_of_sold_asset)
            - flt(row.cost_of_scrapped_asset)
        )

        row.update(
            next(
                asset for asset in assets if asset["name"] == asset_cost.get("name", "")
            )
        )

        row.accumulated_depreciation_as_on_to_date = (
            flt(row.accumulated_depreciation_as_on_from_date)
            + flt(row.depreciation_amount_during_the_period)
            - flt(row.depreciation_eliminated)
        )

        row.net_asset_value_as_on_from_date = flt(row.cost_as_on_from_date) - flt(
            row.accumulated_depreciation_as_on_from_date
        )

        row.net_asset_value_as_on_to_date = flt(row.cost_as_on_to_date) - flt(
            row.accumulated_depreciation_as_on_to_date
        )

        data.append(merge(row, {'doctype': 'Asset'}))

    depreciation_gl_entries = _get_depreciation_gl_entries(filters)
    if depreciation_gl_entries:
        data.append({})

    for gl_entry in depreciation_gl_entries:
        data.append({
            'name': gl_entry.get('name'),
            'cost_as_on_from_date': 0,
            'cost_of_new_purchase': 0,
            'cost_of_sold_asset': 0,
            'cost_of_scrapped_asset': 0,
            'cost_as_on_to_date': 0,
            'accumulated_depreciation_as_on_from_date': 0,
            'depreciation_amount_during_the_period': gl_entry.get('debit'),
            'depreciation_eliminated_during_the_period': 0,
            'accumulated_depreciation_as_on_to_date': 0,
            'net_asset_value_as_on_from_date': 0,
            'net_asset_value_as_on_to_date': 0,
            'doctype': 'GL Entry',
        })

    return data


def _get_asset_costs(filters):
    ac_clause = (
        "AND asset_category = %(asset_category)s"
        if filters.get("asset_category")
        else ""
    )
    return frappe.db.sql(
        """
        SELECT asset_name, name,
			   ifnull(sum(case when purchase_date < %(from_date)s then
							   case when ifnull(disposal_date, 0) = 0 or disposal_date >= %(from_date)s then
									gross_purchase_amount
							   else
									0
							   end
						   else
								0
						   end), 0) as cost_as_on_from_date,
			   ifnull(sum(case when purchase_date >= %(from_date)s then
			   						gross_purchase_amount
			   				   else
			   				   		0
			   				   end), 0) as cost_of_new_purchase,
			   ifnull(sum(case when ifnull(disposal_date, 0) != 0
			   						and disposal_date >= %(from_date)s
			   						and disposal_date <= %(to_date)s then
							   case when status = "Sold" then
							   		gross_purchase_amount
							   else
							   		0
							   end
						   else
								0
						   end), 0) as cost_of_sold_asset,
			   ifnull(sum(case when ifnull(disposal_date, 0) != 0
			   						and disposal_date >= %(from_date)s
			   						and disposal_date <= %(to_date)s then
							   case when status = "Scrapped" then
							   		gross_purchase_amount
							   else
							   		0
							   end
						   else
								0
						   end), 0) as cost_of_scrapped_asset
		from `tabAsset`
		where docstatus=1 
		and company=%(company)s 
		and purchase_date <= %(to_date)s
		{ac_clause}
		group by name
	""".format(
            ac_clause=ac_clause
        ),
        filters,
        as_dict=1,
    )


def _get_assets(filters):
    ac_clause = (
        "WHERE results.asset_category = %(asset_category)s"
        if filters.get("asset_category")
        else ""
    )
    return frappe.db.sql(
        """
		SELECT results.name, results.asset_category,
			   sum(results.accumulated_depreciation_as_on_from_date) as accumulated_depreciation_as_on_from_date,
			   sum(results.depreciation_eliminated_during_the_period) as depreciation_eliminated_during_the_period,
			   sum(results.depreciation_amount_during_the_period) as depreciation_amount_during_the_period
		from (SELECT a.name, a.asset_category,
				   ifnull(sum(a.opening_accumulated_depreciation +
							  case when ds.schedule_date < %(from_date)s and
										(ifnull(a.disposal_date, 0) = 0 or a.disposal_date >= %(from_date)s) then
								   ds.depreciation_amount
							  else
								   0
							  end), 0) as accumulated_depreciation_as_on_from_date,
				   ifnull(sum(case when ifnull(a.disposal_date, 0) != 0 and a.disposal_date >= %(from_date)s
										and a.disposal_date <= %(to_date)s and ds.schedule_date <= a.disposal_date then
								   ds.depreciation_amount
							  else
								   0
							  end), 0) as depreciation_eliminated_during_the_period,

				   ifnull(sum(case when ds.schedule_date >= %(from_date)s and ds.schedule_date <= %(to_date)s
										and (ifnull(a.disposal_date, 0) = 0 or ds.schedule_date <= a.disposal_date) then
								   ds.depreciation_amount
							  else
								   0
							  end), 0) as depreciation_amount_during_the_period
			from `tabAsset` a, `tabDepreciation Schedule` ds
			where a.docstatus=1 and a.company=%(company)s and a.purchase_date <= %(to_date)s and a.name = ds.parent
			group by a.name
			union
			SELECT a.name, a.asset_category,
				   ifnull(sum(case when ifnull(a.disposal_date, 0) != 0
										and (a.disposal_date < %(from_date)s or a.disposal_date > %(to_date)s) then
									0
							   else
									a.opening_accumulated_depreciation
							   end), 0) as accumulated_depreciation_as_on_from_date,
				   ifnull(sum(case when a.disposal_date >= %(from_date)s and a.disposal_date <= %(to_date)s then
								   a.opening_accumulated_depreciation
							  else
								   0
							  end), 0) as depreciation_eliminated_during_the_period,
				   0 as depreciation_amount_during_the_period
			from `tabAsset` a
			where a.docstatus=1 and a.company=%(company)s and a.purchase_date <= %(to_date)s
			and not exists(select * from `tabDepreciation Schedule` ds where a.name = ds.parent)
			group by a.name) as results
        {ac_clause}
		group by results.name
		""".format(
            ac_clause=ac_clause
        ),
        filters,
        as_dict=1,
    )


def _get_depreciation_gl_entries(filters):
    depreciation_account = frappe.db.get_single_value(
        "POS Bahrain Settings", "depreciation_account"
    )
    return frappe.db.sql(
        """
        SELECT name, debit FROM `tabGL Entry`
        WHERE account = %(account)s
        AND against_voucher_type IS NULL
        AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """,
        {
            "account": depreciation_account,
            "from_date": filters.get("from_date"),
            "to_date": filters.get("to_date"),
        },
        as_dict=1,
    )
