/** @odoo-module **/
/**
 * PoS Barcode Handler — intercepts hardware scanner input on the
 * product.barcode.line tree widget and routes it to the active row's
 * barcode field. Works alongside the native Odoo barcode bus.
 */
import { patch } from "@web/core/utils/patch";
import { BarcodeScanner } from "@barcodes/components/barcode_scanner";

patch(BarcodeScanner.prototype, {
	/**
	 * Override _onBarcodeScanned to also dispatch a custom DOM event
	 * so the product barcode list widget can capture scans in-place.
	 */
	_onBarcodeScanned(barcode) {
		// Emit a CustomEvent for any listening barcode field widgets
		document.dispatchEvent(
			new CustomEvent("pharmacy_barcode_scanned", {
				bubbles: true,
				detail: { barcode },
			})
		);
		return super._onBarcodeScanned(barcode);
	},
});