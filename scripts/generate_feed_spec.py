"""Generate the formal AutoNova AI Inventory Data Feed Specification (.docx)."""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

INK = RGBColor(0x0F, 0x17, 0x2A)
ACCENT = RGBColor(0x2D, 0x6C, 0xF6)
GREY = RGBColor(0x55, 0x5B, 0x66)
LIGHT = RGBColor(0x8A, 0x90, 0x9C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

doc = Document()
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0x25, 0x2A, 0x33)
normal.paragraph_format.space_after = Pt(8)
normal.paragraph_format.line_spacing = 1.15

mono = doc.styles.add_style("Mono", 1)
mono.font.name = "Consolas"
mono.font.size = Pt(9.5)
mono.font.color.rgb = INK


def set_cell_bg(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def add_heading(text, size=15, color=INK, space_before=16, space_after=6, rule=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = color
    if rule:
        pPr = p._p.get_or_add_pPr()
        pbdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "6")
        bottom.set(qn("w:color"), "2D6CF6")
        pbdr.append(bottom)
        pPr.append(pbdr)
    return p


def add_sub(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.size = Pt(12)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    return p


def add_body(text, space_after=8):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.add_run(text)
    return p


def add_bullet(text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.font.bold = True
        r.font.color.rgb = INK
        p.add_run(text)
    else:
        p.add_run(text)
    return p


def add_code(text):
    p = doc.add_paragraph(style="Mono")
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.left_indent = Inches(0.15)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F1F5FB")
    pPr.append(shd)
    p.add_run(text)
    return p


# ---- COVER ----
for _ in range(3):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("AUTONOVA AI"); r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = INK
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Inventory Data Feed Specification"); r.font.size = Pt(18); r.font.color.rgb = ACCENT
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("File format, required fields & secure delivery methods for dealership inventory exports")
r.font.size = Pt(11.5); r.font.italic = True; r.font.color.rgb = GREY
for _ in range(6):
    doc.add_paragraph()
meta = doc.add_table(rows=5, cols=2); meta.alignment = WD_TABLE_ALIGNMENT.CENTER
meta_data = [
    ("Prepared for", "Renaud, Yves & DMS / Inventory Provider"),
    ("Prepared by", "Development Team \u2014 AutoNova AI"),
    ("Document", "Inventory Data Feed Specification v1.0"),
    ("Date", "June 2026"),
    ("Status", "Confidential \u2014 For Integration"),
]
for i, (k, v) in enumerate(meta_data):
    c0, c1 = meta.cell(i, 0), meta.cell(i, 1)
    c0.width = Inches(1.9); c1.width = Inches(3.8)
    r0 = c0.paragraphs[0].add_run(k); r0.font.bold = True; r0.font.size = Pt(10); r0.font.color.rgb = WHITE
    set_cell_bg(c0, "0F172A")
    r1 = c1.paragraphs[0].add_run(v); r1.font.size = Pt(10); r1.font.color.rgb = INK
    set_cell_bg(c1, "EEF3FF")
doc.add_page_break()

# ---- 1. PURPOSE ----
add_heading("1.  Purpose")
add_body(
    "This document defines the exact file format and delivery options for supplying dealership vehicle "
    "inventory to the AutoNova AI platform. It is intended for the dealership's DMS or inventory provider "
    "who will prepare and deliver the inventory export. Following this specification ensures each export is "
    "ingested automatically, matched to sellers correctly, and kept up to date with no manual intervention."
)

# ---- 2. FILE FORMAT ----
add_heading("2.  File Format")
add_bullet("Comma-separated values (.csv).", bold_prefix="File type \u2014 ")
add_bullet("UTF-8 (without BOM preferred).", bold_prefix="Encoding \u2014 ")
add_bullet("Comma (,). Fields containing commas must be wrapped in double quotes.", bold_prefix="Delimiter \u2014 ")
add_bullet("The first row must contain the exact column names listed in Section 3 (lower-case, snake_case).", bold_prefix="Header row \u2014 ")
add_bullet("One vehicle per row.", bold_prefix="Rows \u2014 ")
add_bullet("stock_number is the unique key. A repeated stock_number updates the existing record (see Section 6).", bold_prefix="Uniqueness \u2014 ")
add_bullet("No enforced limit, but files may be split by batch if preferred.", bold_prefix="Max size \u2014 ")

# ---- 3. COLUMN SPEC ----
add_heading("3.  Column Specification")
add_body(
    "Column names must match exactly. Required columns must be present in the header and populated on every "
    "row. Optional columns may be omitted entirely or left blank per row."
)

col_table = doc.add_table(rows=1, cols=4)
col_table.style = "Light Grid Accent 1"
for cell, text in zip(col_table.rows[0].cells, ("Column", "Type", "Required", "Description")):
    set_cell_bg(cell, "0F172A")
    run = cell.paragraphs[0].add_run(text)
    run.font.bold = True; run.font.color.rgb = WHITE; run.font.size = Pt(9.5)

cols = [
    ("stock_number", "text", "Yes", "Unique dealer stock / reference number. Primary key for updates."),
    ("make", "text", "Yes", "Manufacturer, e.g. Honda, Toyota, Ford."),
    ("model", "text", "Yes", "Model name, e.g. CR-V, Corolla, F-150."),
    ("year", "integer", "Yes", "Model year, 4 digits, e.g. 2022."),
    ("price", "number", "Yes", "Listing price in dollars, digits only (no $ or commas), e.g. 34999."),
    ("vin", "text", "Optional", "17-character Vehicle Identification Number."),
    ("trim", "text", "Optional", "Trim level, e.g. EX-L, LE, Limited."),
    ("mileage", "integer", "Optional", "Odometer reading, digits only, e.g. 28000."),
    ("body_type", "text", "Optional", "e.g. SUV, Sedan, Truck, Coupe."),
    ("fuel_type", "text", "Optional", "e.g. gas, diesel, hybrid, electric."),
    ("transmission", "text", "Optional", "e.g. automatic, manual."),
    ("drivetrain", "text", "Optional", "e.g. FWD, RWD, AWD, 4WD."),
    ("exterior_colour", "text", "Optional", "e.g. Silver, Black, White."),
    ("seating_capacity", "integer", "Optional", "Number of seats, e.g. 5."),
    ("location", "text", "Optional", "Lot or branch name, e.g. Main Lot."),
    ("status", "text", "Optional", "available (default) or sold / unavailable."),
    ("vehicle_url", "url", "Optional", "Link to the vehicle detail page."),
    ("image_url", "url", "Optional", "Link to the primary vehicle image."),
]
for name, typ, req, desc in cols:
    cells = col_table.add_row().cells
    rc = cells[0].paragraphs[0].add_run(name); rc.font.name = "Consolas"; rc.font.size = Pt(9.5); rc.font.bold = True; rc.font.color.rgb = INK
    cells[1].paragraphs[0].add_run(typ).font.size = Pt(9.5)
    rq = cells[2].paragraphs[0].add_run(req); rq.font.size = Pt(9.5); rq.font.bold = (req == "Yes")
    rq.font.color.rgb = ACCENT if req == "Yes" else GREY
    cells[3].paragraphs[0].add_run(desc).font.size = Pt(9.5)

# ---- 4. SAMPLE FILE ----
add_heading("4.  Sample File")
add_body("A minimal, valid example (header row plus two vehicles):")
add_code("stock_number,vin,year,make,model,trim,price,mileage,body_type,fuel_type,"
         "transmission,drivetrain,exterior_colour,seating_capacity,location,status,vehicle_url,image_url")
add_code("A1234,1HGCM82633A004352,2022,Honda,CR-V,EX-L,34999,28000,SUV,gas,automatic,AWD,"
         "Silver,5,Main Lot,available,https://example.com/v/a1234,https://example.com/img/a1234.jpg")
add_code("A1235,2T1BURHE0JC001234,2021,Toyota,Corolla,LE,22999,41000,Sedan,gas,automatic,FWD,"
         "White,5,Main Lot,available,https://example.com/v/a1235,https://example.com/img/a1235.jpg")
add_body(
    "A ready-to-use blank template with this exact header is available inside the AutoNova AI dashboard "
    "under Inventory \u2192 Template.", space_after=4
)

# ---- 5. DELIVERY METHODS ----
add_heading("5.  Delivery Methods")
add_body("Inventory can be delivered to AutoNova AI in one of two ways. Method A is recommended.")

add_sub("Method A \u2014 Secure HTTPS Push (recommended)")
add_body(
    "AutoNova AI exposes a per-dealership secure endpoint. The provider sends the CSV to this URL over HTTPS "
    "and inventory syncs automatically within seconds. The endpoint is protected by a private access key that "
    "is embedded in the URL, so it must be handled like a password and only shared over secure channels."
)
add_bullet("Retrieved from the dashboard under Inventory \u2192 Data feed (\u201cPush URL\u201d).", bold_prefix="Where to get it \u2014 ")
add_bullet("HTTP POST, multipart/form-data, with the CSV attached under the field name \u201cfile\u201d.", bold_prefix="Method \u2014 ")
add_bullet("The access key can be rotated at any time from the dashboard; the old URL stops working immediately.", bold_prefix="Rotation \u2014 ")
add_body("Example (command line):")
add_code('curl -X POST "https://<your-domain>/api/inventory/feed?token=<ACCESS_KEY>" \\\n'
         '     -F "file=@inventory_export.csv"')
add_body(
    "The key may alternatively be sent as an HTTP header named X-Feed-Token instead of in the URL query string, "
    "if the provider prefers to keep it out of the URL.", space_after=4
)
add_bullet("A second \u201cfull snapshot\u201d URL (same address with &mode=full) is available in the dashboard. Use it when sending the complete current inventory \u2014 any feed vehicle absent from that file is automatically marked unavailable (see Section 6). Use the plain URL for partial/incremental updates.", bold_prefix="Full vs incremental \u2014 ")

add_sub("Method B \u2014 SFTP Drop (client-hosted)")
add_body(
    "If the provider must deliver via SFTP, the SFTP endpoint is hosted and managed on the dealership's side as "
    "separate infrastructure (it is not part of the AutoNova AI web application). Files dropped into the SFTP "
    "folder are then forwarded into AutoNova AI using the Method A push endpoint by a small scheduled job. "
    "Recommended setup:"
)
add_bullet("Stand up a managed SFTP endpoint (e.g. AWS Transfer Family, Files.com, or an SFTP Gateway) writing to a private cloud storage bucket/folder.", bold_prefix="1.  ")
add_bullet("Create a dedicated SFTP user for the provider with write-only access to a single upload folder.", bold_prefix="2.  ")
add_bullet("Enforce SSH key-based authentication (preferred over passwords) and restrict access by IP where possible.", bold_prefix="3.  ")
add_bullet("Schedule a job (e.g. every 15\u201360 minutes) that picks up new .csv files and POSTs each to the AutoNova AI push URL from Method A, then archives the processed file.", bold_prefix="4.  ")
add_bullet("Provide the provider with: host, port (22), username, the public-key fingerprint, and the target folder path.", bold_prefix="5.  ")
add_body(
    "This keeps the provider on the SFTP workflow they requested while inventory still lands in AutoNova AI "
    "through the same validated import path.", space_after=4
)

# ---- 6. SYNC BEHAVIOUR ----
add_heading("6.  Sync Behaviour & Validation")
add_bullet("Each row is matched by stock_number. If it already exists, the record is updated; otherwise a new vehicle is created (upsert).", bold_prefix="Upsert \u2014 ")
add_bullet("Rows missing a stock_number or make are skipped and reported; valid rows in the same file still import.", bold_prefix="Partial success \u2014 ")
add_bullet("Every delivery returns a summary of created, updated, and skipped rows. Recent syncs are visible in the dashboard under Inventory \u2192 Data feed.", bold_prefix="Reporting \u2014 ")
add_bullet("When delivering via the full-snapshot URL (&mode=full), send the entire current inventory in one file; any feed-sourced vehicle missing from that file is automatically set to status = unavailable and removed from matching. The incremental URL never removes vehicles.", bold_prefix="Removals \u2014 ")
add_bullet("Prices and mileage must be digits only. Non-numeric values in numeric fields cause that single row to be skipped and reported.", bold_prefix="Data types \u2014 ")

# ---- 7. CHECKLIST ----
add_heading("7.  Provider Checklist")
for item in [
    "Export saved as UTF-8 CSV with the exact header row from Section 3.",
    "All five required columns present and populated on every row.",
    "Prices and mileage contain digits only (no currency symbols or thousands separators).",
    "Full current inventory included; sold vehicles marked accordingly.",
    "Delivery method confirmed (HTTPS push URL received, or SFTP endpoint configured).",
    "A test file of 5\u201310 vehicles sent first to confirm a clean sync before the full export.",
]:
    add_bullet(item)

doc.add_paragraph()
c = doc.add_paragraph()
r = c.add_run("Questions on any field or delivery option can be directed to the AutoNova AI development team. "
              "We recommend starting with a small test file to validate the end-to-end sync before the first "
              "full inventory load.")
r.font.italic = True; r.font.color.rgb = GREY; r.font.size = Pt(10.5)

# Footer
footer = doc.sections[0].footer
fp = footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fr = fp.add_run("AutoNova AI  \u2022  Inventory Data Feed Specification v1.0  \u2022  Confidential")
fr.font.size = Pt(8); fr.font.color.rgb = LIGHT

out = "/app/frontend/public/AutoNova_AI_Inventory_Data_Feed_Specification.docx"
doc.save(out)
print("Saved:", out)
