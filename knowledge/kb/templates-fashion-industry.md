---
id: kb_templates_fashion
type: kb
title: Templates for Fashion and Apparel (Recommended Fields + Layout)
visibility: public
tags: [templates, fashion, apparel, footwear, tags, packaging, fields, mrp, sku, barcode, qr]
industries: [fashion, footwear, lifestyle]
canonical_url: /help/templates/fashion
updated_at: 2026-03-06
---

# Templates for Fashion and Apparel (Recommended Fields + Layout)

This guide helps you create practical, print-ready templates for **fashion/apparel** brands—covering:
- hang tags (retail tags)
- packaging stickers
- carton labels (optional)

The goal is to help you build templates that are:
- consistent across SKUs
- easy to generate in bulk
- readable and scannable in real-world use

---

## 1) Fashion hang tag template (most common)

### Typical use
- retail tags for garments
- tags used in photoshoots, warehouse packing, offline retail

### Recommended fields (minimum)
- **Brand name / logo**
- **Product name** (or short name)
- **SKU**
- **Size**
- **Color / Variant** (if needed)
- **MRP**
- **Country of origin** (if you show it)
- **Barcode or QR** (if you scan in warehouse/store)

### Optional fields (nice to have)
- Fabric / material composition (e.g., “100% Cotton”)
- Care instructions (wash symbols or text)
- Collection name / season
- Customer care contact (email/website)
- “Packed on” / date fields (if you track)

---

## 2) Packaging sticker template (for polybags / pouches / boxes)

### Typical use
- internal warehouse labeling
- packing identification
- channel-specific packaging

### Recommended fields
- Brand
- SKU
- Product name
- Size/variant
- Quantity (if packing multiple units)
- Barcode/QR (optional but useful)

---

## 3) Carton label template (for wholesale / logistics)

### Typical use
- outer cartons used for wholesale or inter-city shipment
- batch identification

### Recommended fields
- Brand
- Carton ID (or batch ID)
- SKU(s) inside (single SKU carton) OR “mixed”
- Sizes/variants
- Quantity inside carton
- Warehouse/dispatch date (optional)
- Barcode/QR for carton ID (highly recommended)

---

## Template design tips (fashion-specific)

### Keep it readable
Hang tags are often small. Prioritize:
- Product name
- Size
- MRP
- SKU

### Barcode placement
- Put barcode/QR away from tag edges
- Ensure enough whitespace around code
- Test scan after printing

### Standardize naming and fields
Use consistent field names across templates:
- `sku`, `product_name`, `size`, `mrp`, `color`

This makes bulk generation and reuse much easier.

---

## Suggested template set for a fashion brand (starter pack)
A good starting set is:
1. `Hang Tag - Standard (MRP + Size + SKU)`
2. `Packaging Sticker - Warehouse`
3. `Carton Label - Wholesale/Dispatch`

---

## Bulk generation guidance (fashion)
For bulk runs, structure your input rows like:
- sku
- product_name (or short_name)
- size
- color
- mrp
- barcode_value (if used)

✅ Tip: If product names are long, prefer a `short_name` field to avoid layout overflow.

---

- label type (hang tag / packaging / carton)
- your required fields
- approximate print size (or a photo of your current tag)
