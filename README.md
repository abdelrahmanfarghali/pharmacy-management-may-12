# pharmacy_consignment — SC3-UC-02
## Consignment Purchase (التصريف تحت بضاعة) — Odoo v18

---

### Overview

This module implements the full consignment purchase workflow for pharmacies running Odoo 18.
A purchasing officer or pharmacy manager can flag any Purchase Order as **Consignment**, receive
goods into the warehouse, and pay the supplier **only for units actually sold**, cycle by cycle.

---

### Features

| Feature | Details |
|---|---|
| **Consignment Flag** | Boolean checkbox on PO form header, read-only after confirmation |
| **CONSIGNMENT Banner** | Orange banner on PO form + column in list view |
| **Track Stock Button** | Opens wizard pop-up on consignment POs only |
| **Track Stock Wizard** | Per-product: Received / Sold / Already Paid / Payable Now (locked 🔒) |
| **Partial Payment** | Creates a locked vendor bill for exactly Payable Now qty |
| **Already Paid Tracking** | Custom model accumulates paid qty per PO line across cycles |
| **Chatter Logging** | Flag set/removed, each payment bill, return transfers all logged |
| **Unsold Return** | Standard Odoo return transfer — no custom logic needed |
| **Normal PO unchanged** | Non-consignment POs have zero modifications |

---

### Installation

1. Copy `pharmacy_consignment/` folder to your Odoo **addons** path.
2. Restart the Odoo server.
3. In **Settings → Apps**, enable developer mode, then search for **Pharmacy Consignment** and install.

**Required dependencies** (must already be installed):
- `purchase`
- `stock`
- `account`
- `sale_management`
- `point_of_sale`

---

### Usage Workflow

#### Step 1 — Create a Consignment PO
1. Go to **Purchase → Orders → Purchase Orders → New**.
2. Select a Vendor.
3. Check **"Consignment (التصريف تحت بضاعة)"** checkbox (below the Vendor field).
4. Add product lines and confirm the PO.
5. The **CONSIGNMENT** banner appears and the checkbox becomes read-only.

#### Step 2 — Receive Goods
- Process the incoming shipment normally (Validate the receipt).
- **Received Quantity** is now tracked against the PO.

#### Step 3 — Track Stock (after sales)
1. Open the confirmed consignment PO.
2. Click **🔍 Track Stock** in the toolbar.
3. The wizard shows for each product:
   - **Received Quantity** — from validated pickings
   - **Sold Quantity** — from SO lines + POS lines since receipt date
   - **Already Paid Quantity** — from previous payment cycles
   - **Payable Now** 🔒 — computed (Sold − Already Paid), read-only, locked

#### Step 4 — Create Partial Payment
1. In the Track Stock wizard, click **💳 PAYMENT — Sold and Unpaid Qty Only**.
2. A vendor bill is auto-created with quantities locked to Payable Now.
3. The bill is pre-filled: vendor, PO reference, products, quantities, prices.
4. **You cannot change the quantity** on the bill — it is locked to Payable Now.
5. Post and pay the bill normally.
6. **Already Paid Quantity** is automatically updated for the next cycle.

#### Step 5 — Return Unsold Stock (if needed)
- Use standard **Inventory → Transfers → Return** to create a return transfer.
- The return automatically reduces **Received Quantity** in the wizard.
- A chatter note is logged: *"Return transfer [REF] created — Remaining Quantity updated."*

---

### Technical Details

#### New Models

| Model | Purpose |
|---|---|
| `purchase.order.line.consignment.payment` | Tracks cumulative paid qty per PO line |
| `consignment.track.stock.wizard` | Transient wizard (pop-up) |
| `consignment.track.stock.wizard.line` | One line per product in wizard |

#### Extended Models

| Model | Changes |
|---|---|
| `purchase.order` | `is_consignment` Boolean field, `action_track_consignment_stock()` |
| `purchase.order.line` | Computed qty fields, `_get_sold_qty()`, `_get_receipt_date()` |
| `account.move` | `consignment_po_id` link, `is_consignment_bill` flag |
| `stock.picking` | Logs chatter on return validation for consignment POs |

#### Sold Quantity Computation
`_get_sold_qty()` queries **both**:
- `sale.order.line` — confirmed/done sale orders
- `pos.order.line` — done/invoiced POS orders

Filtered by product and date ≥ PO first receipt date. UoM conversion applied automatically.

---

### File Structure

```
pharmacy_consignment/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── purchase_order.py                      # PO + PO Line extensions
│   └── purchase_order_line_consignment.py     # Payment tracking model
├── wizard/
│   ├── __init__.py
│   ├── track_stock_wizard.py                  # Wizard models + account.move/stock.picking ext
│   └── track_stock_wizard_views.xml           # Wizard form view
├── views/
│   ├── purchase_order_views.xml               # PO form (banner, button, checkbox)
│   └── purchase_order_list_views.xml          # PO list + search filters
├── security/
│   └── ir.model.access.csv                    # Access rights
├── data/
│   └── consignment_data.xml                   # Server action
└── static/src/scss/
    └── consignment.scss                        # Custom styles
```

---

### Acceptance Criteria Checklist

- [x] Consignment checkbox on PO form (near Vendor field)
- [x] Checkbox read-only after PO confirmation
- [x] Normal PO unaffected when checkbox unchecked
- [x] CONSIGNMENT banner on form and list view
- [x] Chatter log when flag is set/removed
- [x] Track Stock button visible on consignment POs only
- [x] Track Stock wizard: Received / Sold / Already Paid / Payable Now per product
- [x] Payable Now is read-only and locked (cannot be edited)
- [x] PAYMENT button greyed out when Payable Now = 0
- [x] Partial vendor bill created with locked quantities
- [x] Bill pre-filled: vendor, PO ref, products, Payable Now qty, unit price
- [x] Already Paid Quantity updated after each payment cycle
- [x] Multiple partial payments supported over time
- [x] All bills linked to original PO (visible in Bills smart button)
- [x] Unsold return via standard Odoo return transfer
- [x] Return reduces Received Quantity in wizard automatically
- [x] Chatter log on return transfer

---

*Odoo v18 | Pharmacy System — Advanced Product Configuration Phase 2 | SC3-UC-02*
