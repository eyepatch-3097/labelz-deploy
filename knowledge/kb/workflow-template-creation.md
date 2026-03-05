---
id: kb_workflow_template_creation
type: kb
title: Workflow: Template Creation in Labelz
visibility: public
tags: [workflow, templates, template_design, setup, labeling]
industries: [fashion, footwear, beauty, food, handmade, gifting, home_decor, lifestyle]
canonical_url: /help/workflows/template-creation
updated_at: 2026-03-06
---

# Workflow: Template Creation in Labelz

A **Template** is a reusable base you create once and use many times to generate labels.  
A good template helps you generate **consistent, print-ready labels**—whether you’re printing 1 label or 5,000.

This guide covers creating a template the right way so it’s reusable and scalable.

---

## Before you start (recommended)
Decide these first:
- What are you creating?
  - **Product tag** (hang tag / clothing tag)
  - **Packaging label** (pouch / bottle / box)
  - **Carton label** (outer packaging / logistics)
- What fields do you need on the label?
  - SKU, Product name, Variant, Size, MRP
  - Net qty, batch, MFD/EXP (for food/beauty)
  - Barcode / QR code (if you need scanning)

---

## Step-by-step: Create a Template

### Step 1 — Go to the right Org and Workspace
1. Select your **Org**
2. Open the **Workspace** where you want this template stored  
   (Example: `Retail Tags` or `Amazon Packaging`)

✅ This ensures the template stays organized and visible to the right team.

---

### Step 2 — Click “Create Template”
1. Go to **Templates**
2. Click **Create Template**
3. Enter:
   - **Template name** (be specific)
     - Good: `Retail Tag - Cotton Kurta (2026)`
     - Good: `Pouch Label - 250g Granola`
     - Avoid: `Tag 1`, `New Template`

---

### Step 3 — Choose the template type / size (if available)
Depending on your Labelz editor, you may select:
- label type (tag / packaging / carton)
- size or layout preset

If you’re unsure, start with a common practical approach:
- choose a size close to your real sticker/tag dimensions
- you can refine after a test print

---

### Step 4 — Add fields (the “data structure”)
Fields are what will change label-to-label (SKU, size, price, batch, etc.).

Add the fields you expect to populate later:
- **Identity fields**
  - SKU / Product code
  - Product name
  - Variant (size/color)
- **Pricing fields**
  - MRP
- **Compliance / packaging fields** (as needed)
  - Net qty
  - Batch / Lot
  - MFD / EXP
- **Codes**
  - Barcode value
  - QR code value
  - Serialized ID

✅ Tip: Keep field names consistent across templates so bulk uploads and reuse become easier.

---

### Step 5 — Design the layout (Template Design)
Now place your fields + branding into a print-ready layout:
- Add logo / brand name
- Position fields neatly
- Make sure font size is readable on actual printed size
- Place barcode/QR with sufficient quiet-zone/margins

✅ Best practice: do a test print before finalizing spacing.

---

### Step 6 — Save and validate
1. Save the template
2. Generate a **single test label** using sample data
3. Export / print once to verify:
- alignment
- cut-off margins
- barcode/QR scannability
- text readability

---

## Template design checklist (use this every time)

### Print-readiness
- [ ] Nothing important is too close to the edge
- [ ] Font sizes are readable at actual label size
- [ ] Barcode has adequate spacing (quiet zone)
- [ ] QR code is not too small (test scan!)

### Reuse
- [ ] Template name clearly indicates use-case
- [ ] Fields are standardized and not duplicated
- [ ] Works for multiple SKUs/variants (not only one product)

---

## Common mistakes (and how to avoid them)

### “Template looks fine on screen but prints badly”
- Usually a sizing/margin issue.
- Fix by increasing padding/margins and test printing again.

### “Bulk generation becomes messy later”
- Happens when field names are inconsistent (`mrp`, `MRP`, `price_mrp`)
- Use consistent field naming across templates.

### “My barcode/QR isn’t scanning”
- Barcode/QR too small or too close to edge
- Increase size and add more margin around the code

---

## What to do next
✅ Generate a **single label** for testing  
✅ Then do a **bulk generation (batch)** for production runs

