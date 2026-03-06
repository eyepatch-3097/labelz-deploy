---
id: kb_templates_fmcg
type: kb
title: Templates for FMCG (Food, Beauty, and Consumables)
visibility: public
tags: [templates, fmcg, food, beauty, cosmetics, packaging, compliance, batch, mfd, exp, net_qty, mrp, barcode, qr]
industries: [fmcg, food, beauty, cosmetics, lifestyle]
canonical_url: /help/templates/fmcg
updated_at: 2026-03-06
---

# Templates for FMCG (Food, Beauty, and Consumables)

FMCG labels are usually **packaging-first** and often need operational fields like batch and dates.

This guide helps you create templates for:
- food and consumables
- beauty and cosmetics
- small-batch packaged products (D2C brands)

> Important: Compliance fields depend on your category and where you sell. This guide focuses on common practical setups used by small brands.

---

## 1) Food / consumables packaging label template

### Typical use
- pouches, jars, bottles, boxes
- retail packaging labels
- small batch production and restocking

### Recommended fields (common)
- **Brand name / logo**
- **Product name**
- **Variant / flavor** (if applicable)
- **Net quantity** (e.g., 250g)
- **MRP**
- **Batch / Lot number**
- **MFD** (manufacturing date)
- **EXP / Best before**
- **Barcode or QR** (recommended)

### Optional fields
- Ingredients (if you print them here)
- Allergen warning
- Storage instructions
- Customer care info (website/email)
- Veg/Non-veg marking (if applicable)

---

## 2) Beauty / cosmetics packaging label template

### Typical use
- tubes, bottles, jars, boxes
- shade/variant-heavy catalogs

### Recommended fields (common)
- Brand name / logo
- Product name
- Shade / variant
- Net quantity (ml/g)
- MRP
- Batch number
- MFD / EXP (or best before)
- Barcode/QR (recommended)

### Optional fields
- Skin type / usage direction (short)
- “For external use only” warnings (if needed)
- Manufacturer/marketer name (depending on setup)

---

## 3) Inner label vs outer label (practical approach)

Many FMCG brands use two templates:
1) **Primary pack label** (consumer-facing, brand-heavy)
2) **Ops sticker** (simple SKU/batch label for warehouse)

### Ops sticker recommended fields
- SKU
- Product name (short)
- Variant
- Batch
- MFD/EXP
- Barcode/QR (optional)

---

## Template design tips (FMCG-specific)

### Date formatting
Standardize one format across all labels, for example:
- `DD-MM-YYYY` (or your internal standard)

### Make batch and dates prominent
Batch/MFD/EXP are operationally critical during:
- recall
- quality checks
- replacement/reprints

### Keep barcode/QR scannable
- avoid shrinking codes too much to fit content
- ensure whitespace around the code

---

## Suggested FMCG template set (starter pack)

For most D2C FMCG brands, a solid start is:
1. `Primary Pack Label - Food (Net Qty + Batch + Dates + MRP)`
2. `Primary Pack Label - Beauty (Shade + Net Qty + Batch + Dates + MRP)`
3. `Ops Sticker - SKU/Batch`

---

## Bulk generation guidance (FMCG)
For bulk runs, structure rows like:
- sku
- product_name
- variant
- net_qty
- mrp
- batch_no
- mfd
- exp
- barcode_value (optional)

✅ Tip: Validate date format before generating 1000+ labels.

---

