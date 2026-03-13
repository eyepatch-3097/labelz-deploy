
# LabelCraft

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/891a47944c2c4f279766474d3252f2c5)](https://app.codacy.com/gh/eyepatch-3097/labelz-deploy?utm_source=github.com&utm_medium=referral&utm_content=eyepatch-3097/labelz-deploy&utm_campaign=Badge_Grade)

**Design, generate, and print product labels—fast.**  
Labelcraft is a lightweight, workflow-first label system built for retail/D2C teams who want **pixel-perfect templates**, **batch-ready generation**, and **print-friendly output**—without wrestling spreadsheets or design tools.


## Libraries Used

 - [Python Barcode Library](https://python-barcode.readthedocs.io/en/stable/)
 - [QR Code Library](https://github.com/lincolnloop/python-qrcode)


## Deployment

To deploy this project run

```bash
  python -m venv venv
  .venv\Scripts\Activate
  pip install -r requirements.txt
  python manage.py makemigrations
  python manage.py migrate
  python manage.py runserver
```

Or you can check out our existing production deploy at: [Labelcraft](labelcraftdeploy.onrender.com)

## What Labelcraft does

### 1) Template Designer (Canvas-Based)
Create label templates visually using a drag-and-drop canvas.

**You can:**
- Add standard workspace variables (e.g., Product Name, Description, MRP, Category, etc.)
- Add special fields like **Barcode** and **QR Code**
- Add **Static Text** blocks (for fixed branding or compliance notes)
- Add **Shapes** (rectangle / circle / triangle / star) as design elements
- Control each field’s:
  - Position (x/y)
  - Size (width/height)
  - Font styles (bold/italic/underline)
  - Font size
  - Text color + background color
- Set a **Canvas Background Color** for the whole label

✅ Templates are saved and reused across label generation flows.

---

### 2) Single Label / Batch Generation
Once a template is ready, Labelcraft lets you generate labels in seconds.

**Generation flow includes:**
- Enter **EAN code** (mandatory)
- Optional **GS1 data**
- Enter values only for **real variable fields**
- Generate labels in **single mode** or **batch mode** (Qty up to your configured limit)

**Automatically handled by Labelcraft:**
- Barcode generation (PNG)
- QR generation (PNG)
- Serialisation logic for batch output (e.g., `001`, `002`, `003`…)

---

### 3) Preview → Print Workflow
Every generation produces a **preview** and a **print-ready batch output**.

**Print view supports:**
- Paginated label rendering
- Accurate absolute positioning (same coordinates as canvas)
- Batch-by-batch history tracking
- “Download label as PNG” option (where supported)

---

## How it works (Execution Details)

### Data Model (Concept)
Labelcraft centers around:
- **Workspace** → defines the org + available fields
- **Workspace Fields** → variables allowed in templates
- **Label Template** → canvas metadata (size, DPI, background color)
- **Template Fields** → layout items stored with style + field metadata
- **Label Batch** → a saved generation instance, including:
  - EAN/GS1 values
  - quantity
  - field_values payload
  - generated preview + print rendering

---

### Rendering Engine (Concept)
Labelcraft renders labels using:
- A fixed-size canvas (scaled from cm + DPI rules)
- Absolutely positioned field blocks
- Logic-based rendering rules:
  - **Shapes render only shapes**
  - **Barcode/QR render images only**
  - **Static Text renders only static content**
  - **Normal fields render label + value using consistent style rules**
 
## Roadmap

- Additional formatting options
- Global History for ADMIN
- AI Chatbot for Guided Agentic Labelling
- Better Managed Access Control
- UI/UX Optimizations
