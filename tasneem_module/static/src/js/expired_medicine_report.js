/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExpiredMedicineReport extends Component {
    static template = "tasneem_module.ExpiredMedicineReport";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            locations: [],
            selectedLocations: [],
            monthYear: "",
            reportData: [],
            sortColumn: "medicine_name",
            sortAscending: true,
        });

        onWillStart(async () => {
            this.state.locations = await this.orm.searchRead(
                'stock.location',
                [['is_expired_location', '=', true]],
                ['id', 'display_name']
            );
        });
    }

    handleLocationChange(ev) {
        const options = ev.target.options;
        const selected = [];
        for (let i = 0; i < options.length; i++) {
            if (options[i].selected) {
                selected.push(parseInt(options[i].value));
            }
        }
        this.state.selectedLocations = selected;
    }

    async generateReport() {
        let month = null;
        let year = null;
        if (this.state.monthYear) {
            const parts = this.state.monthYear.split('-');
            year = parts[0];
            month = parts[1];
        }

        const data = await this.orm.call('stock.quant', 'get_expired_report_data', [], {
            month: month,
            year: year,
            location_ids: this.state.selectedLocations.length > 0 ? this.state.selectedLocations : null,
        });

        this.state.reportData = data;
        this.sortData();
    }

    async exportPDF() {
        let month = null;
        let year = null;
        if (this.state.monthYear) {
            const parts = this.state.monthYear.split('-');
            year = parts[0];
            month = parts[1];
        }

        let branchName = "All Branches";
        if (this.state.selectedLocations.length === 1) {
            const loc = this.state.locations.find(l => l.id === this.state.selectedLocations[0]);
            if (loc) branchName = loc.display_name;
        } else if (this.state.selectedLocations.length > 1) {
            branchName = "Multiple Branches";
        }

        const data = await this.orm.call('stock.quant', 'get_expired_report_data', [], {
            month: month,
            year: year,
            location_ids: this.state.selectedLocations.length > 0 ? this.state.selectedLocations : null,
        });

        const grandTotal = data.reduce((acc, row) => acc + row.total_price, 0);

        this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'tasneem_module.report_expired_medicine',
            report_file: 'tasneem_module.report_expired_medicine',
            data: {
                report_data: data,
                grand_total: grandTotal,
                branch_name: branchName,
                month_year: this.state.monthYear || 'All Time',
                generation_datetime: new Date().toLocaleString(),
            },
            context: {
                branch_name: branchName,
                month_year: this.state.monthYear || 'All_Time'
            }
        });
    }

    toggleSort(column) {
        if (this.state.sortColumn === column) {
            this.state.sortAscending = !this.state.sortAscending;
        } else {
            this.state.sortColumn = column;
            this.state.sortAscending = true;
        }
        this.sortData();
    }

    sortData() {
        const col = this.state.sortColumn;
        const asc = this.state.sortAscending ? 1 : -1;
        this.state.reportData.sort((a, b) => {
            let valA = a[col];
            let valB = b[col];
            
            // Handle empty dates for sorting
            if (valA === undefined || valA === null) valA = '';
            if (valB === undefined || valB === null) valB = '';

            if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }
            if (valA < valB) return -1 * asc;
            if (valA > valB) return 1 * asc;
            return 0;
        });
    }

    get grandTotal() {
        return this.state.reportData.reduce((acc, row) => acc + row.total_price, 0);
    }
}

registry.category("actions").add("expired_medicine_report_action", ExpiredMedicineReport);
