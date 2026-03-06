---
id: kb_templates_beauty_cosmetics
type: kb
title: Templates for Beauty and Cosmetics (Recommended Fields + Layout)
visibility: public
tags: [templates, beauty, cosmetics, skincare, makeup, packaging, compliance, batch, mfd, exp, net_qty, mrp, barcode, qr]
industries: [beauty, cosmetics, lifestyle, fmcg]
canonical_url: /help/templates/beauty-cosmetics
updated_at: 2026-03-06
---

# Templates for Beauty and Cosmetics (Recommended Fields + Layout)

Beauty/cosmetics labels usually need **variant/shade support**, **net quantity**, and **batch/date fields** for operations and compliance.

This guide covers:
- primary pack labels (consumer-facing)
- ops/warehouse stickers
- carton/dispatch labels (optional)

> Important: Exact compliance requirements depend on your product category and where you sell. This guide focuses on common setups used by D2C brands.

---

## 1) Primary pack label template (consumer-facing)

### Typical use
- jars, bottles, tubes, boxes
- labels visible to customers

### Recommended fields (common)
- **Brand name / logo**
- **Product name**
- **Shade / Variant** (very important)
- **Net quantity** (ml/g)
- **MRP**
- **Batch number**
- **MFD** (manufacturing date)
- **EXP** (expiry date) or **Best before**
- **Barcode or QR** (recommended)

### Optional fields
- Directions for use (short)
- Caution text (short)
- Customer care info (website/email)
- Manufacturer/marketer info (based on your setup)

---

## 2) Ops sticker template (warehouse-friendly)

### Typical use
- quick identification stickers
- used by packing/dispatch teams
- placed on secondary packaging or inside cartons

### Recommended fields
- SKU
- Product name (short)
- Variant / Shade
- Net quantity
- Batch
- MFD/EXP
- Barcode/QR (optional)

**Best practice:** Keep this template simple, large text, minimal branding.

---

## 3) Carton / dispatch label (optional but useful for scaling)

### Recommended fields
- Brand
- Carton ID / Batch ID
- SKU(s) inside (single/mixed)
- Variant summary (if needed)
- Quantity
- Dispatch date (optional)
- Barcode/QR for carton ID

---

## Template design tips (beauty/cosmetics)

### Make “shade/variant” prominent
Most returns and operational confusion happen due to shade mismatch. Keep variant readable.

### Standardize date formats
Pick one format and stick to it across all labels:
- `DD-MM-YYYY` (or your internal standard)

### QR/barcode scannability
Beauty packaging is often curved (bottles/jars). Place codes where they won’t crease or distort.

---

## Suggested template set (starter pack)
1. `Primary Pack Label - Cosmetics (Variant + Net Qty + Dates + Batch + MRP)`
2. `Ops Sticker - Cosmetics (SKU + Variant + Batch + Dates)`
3. `Carton Label - Cosmetics Dispatch`

---

## Bulk generation guidance (beauty/cosmetics)
Recommended bulk row structure:
- sku
- product_name
- variant_or_shade
- net_qty
- mrp
- batch_no
- mfd
- exp
- barcode_value (optional)

✅ Tip: Validate all date formats before generating 1000+ labels.

---
