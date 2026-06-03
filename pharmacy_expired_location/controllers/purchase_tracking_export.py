# -*- coding: utf-8 -*-
import io
import json
from datetime import datetime, date
from odoo import http
from odoo.http import request, content_disposition

class PurchaseTrackingExportController(http.Controller):

    @http.route('/web/purchase_tracking/export_xlsx', type='http', auth='user', methods=['POST', 'GET'])
    def export_xlsx(self, domain, groupby=None, **kw):
        domain = json.loads(domain)
        groupby = json.loads(groupby) if groupby else []
        
        # Search purchase.order.line records matching the domain.
        # Order by groupby field if active, otherwise order by purchase order (order_id)
        order = ', '.join(groupby) if groupby else 'order_id'
        lines = request.env['purchase.order.line'].search(domain, order=order)
        
        output = io.BytesIO()
        
        try:
            import xlsxwriter
        except ImportError:
            return request.not_found()
            
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('PO Tracking')
        
        # Custom styles for a premium design (Corporate Teal Theme)
        header_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 11,
            'font_color': '#FFFFFF',
            'bg_color': '#008080',  # Teal
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#004d4d'
        })
        
        group_header_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 11,
            'font_color': '#004d4d',
            'bg_color': '#E6F2F2',  # Light Teal tint
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#B3D9D9'
        })
        
        group_total_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 10,
            'font_color': '#004d4d',
            'bg_color': '#F2F9F9',  # Lighter Teal tint
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#B3D9D9',
            'num_format': '#,##0.00'
        })

        group_total_label_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 10,
            'font_color': '#004d4d',
            'bg_color': '#F2F9F9',
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#B3D9D9'
        })
        
        data_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E0E0E0'
        })

        number_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E0E0E0',
            'num_format': '#,##0.00'
        })
        
        date_format_cell = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E0E0E0',
            'num_format': 'yyyy-mm-dd'
        })

        # Columns
        headers = [
            'Product',
            'Qty. Ordered',
            'Qty. Received',
            'Qty. Not Received',
            'Confirmation Date',
            'Expected Arrival'
        ]
        
        # Write headers
        worksheet.set_row(0, 25)
        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header, header_format)
            
        row_idx = 1
        
        if groupby:
            # We group by the first groupby field
            groupby_field = groupby[0]
            
            # Let's group the records
            grouped_lines = {}
            for line in lines:
                val = line[groupby_field]
                # If val is a recordset (like order_id, partner_id), use display_name or ID
                if hasattr(val, 'display_name'):
                    key = val.display_name or 'Undefined'
                elif isinstance(val, (datetime, date)):
                    key = val.strftime('%Y-%m-%d')
                else:
                    key = str(val) if val is not False else 'Undefined'
                grouped_lines.setdefault(key, []).append(line)
                
            for group_name, group_records in grouped_lines.items():
                # Write group header row
                worksheet.set_row(row_idx, 22)
                # Field label
                field_label = request.env['purchase.order.line'].fields_get([groupby_field])[groupby_field].get('string', groupby_field.replace('_', ' ').title())
                worksheet.merge_range(row_idx, 0, row_idx, 5, f" {field_label}: {group_name}", group_header_format)
                group_start_row = row_idx + 2  # Excel rows are 1-based (row_idx is 0-based index)
                row_idx += 1
                
                # Write data rows
                for line in group_records:
                    worksheet.set_row(row_idx, 20)
                    product_label = line.list_name or line.product_id.display_name or ''
                    worksheet.write(row_idx, 0, product_label, data_format)
                    worksheet.write(row_idx, 1, line.qty_invoiced, number_format)
                    worksheet.write(row_idx, 2, line.qty_received, number_format)
                    worksheet.write(row_idx, 3, line.qty_not_received, number_format)
                    
                    date_approve_val = line.date_approve.strftime('%Y-%m-%d') if line.date_approve else ''
                    date_planned_val = line.date_planned.strftime('%Y-%m-%d') if line.date_planned else ''
                    worksheet.write(row_idx, 4, date_approve_val, date_format_cell)
                    worksheet.write(row_idx, 5, date_planned_val, date_format_cell)
                    row_idx += 1
                    
                # Write group total row
                group_end_row = row_idx  # 1-based row number for formula is the row_idx index itself because of header row offset
                worksheet.set_row(row_idx, 22)
                worksheet.write(row_idx, 0, f" Total {group_name}", group_total_label_format)
                
                # Use formulas for totals
                worksheet.write_formula(row_idx, 1, f"=SUM(B{group_start_row}:B{group_end_row})", group_total_format)
                worksheet.write_formula(row_idx, 2, f"=SUM(C{group_start_row}:C{group_end_row})", group_total_format)
                worksheet.write_formula(row_idx, 3, f"=SUM(D{group_start_row}:D{group_end_row})", group_total_format)
                worksheet.write(row_idx, 4, "", group_total_format)
                worksheet.write(row_idx, 5, "", group_total_format)
                row_idx += 1
        else:
            # No groupby, just write a flat list and one overall total
            start_row = 2
            for line in lines:
                worksheet.set_row(row_idx, 20)
                product_label = line.list_name or line.product_id.display_name or ''
                worksheet.write(row_idx, 0, product_label, data_format)
                worksheet.write(row_idx, 1, line.qty_invoiced, number_format)
                worksheet.write(row_idx, 2, line.qty_received, number_format)
                worksheet.write(row_idx, 3, line.qty_not_received, number_format)
                
                date_approve_val = line.date_approve.strftime('%Y-%m-%d') if line.date_approve else ''
                date_planned_val = line.date_planned.strftime('%Y-%m-%d') if line.date_planned else ''
                worksheet.write(row_idx, 4, date_approve_val, date_format_cell)
                worksheet.write(row_idx, 5, date_planned_val, date_format_cell)
                row_idx += 1
                
            # Write overall total
            worksheet.set_row(row_idx, 22)
            worksheet.write(row_idx, 0, " Total", group_total_label_format)
            worksheet.write_formula(row_idx, 1, f"=SUM(B{start_row}:B{row_idx})", group_total_format)
            worksheet.write_formula(row_idx, 2, f"=SUM(C{start_row}:C{row_idx})", group_total_format)
            worksheet.write_formula(row_idx, 3, f"=SUM(D{start_row}:D{row_idx})", group_total_format)
            worksheet.write(row_idx, 4, "", group_total_format)
            worksheet.write(row_idx, 5, "", group_total_format)
            row_idx += 1

        # Adjust column widths
        worksheet.set_column(0, 0, 45)  # Product
        worksheet.set_column(1, 1, 15)  # Qty. Ordered
        worksheet.set_column(2, 2, 15)  # Qty. Received
        worksheet.set_column(3, 3, 18)  # Qty. Not Received
        worksheet.set_column(4, 4, 18)  # Confirmation Date
        worksheet.set_column(5, 5, 18)  # Expected Arrival
        
        # Grid lines visible
        worksheet.hide_gridlines(0)

        workbook.close()
        output.seek(0)
        
        filename = "Purchase_Order_Tracking.xlsx"
        xlsxheader = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename))
        ]
        return request.make_response(output.read(), headers=xlsxheader)
