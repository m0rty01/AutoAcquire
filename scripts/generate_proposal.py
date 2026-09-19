"""Generate a formal AutoNova AI Project Scope & Requirements Proposal (.docx)."""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Brand palette
INK = RGBColor(0x0F, 0x17, 0x2A)      # deep navy
ACCENT = RGBColor(0x2D, 0x6C, 0xF6)   # electric blue
GREY = RGBColor(0x55, 0x5B, 0x66)
LIGHT = RGBColor(0x8A, 0x90, 0x9C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

doc = Document()

# ---- Base styles ----
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor(0x25, 0x2A, 0x33)
normal.paragraph_format.space_after = Pt(8)
normal.paragraph_format.line_spacing = 1.15

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
    r.font.name = "Calibri"
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

def add_subheading(text):
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

# =========================================================================
# COVER
# =========================================================================
for _ in range(3):
    doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("AUTONOVA AI")
r.font.size = Pt(40)
r.font.bold = True
r.font.color.rgb = INK

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Project Scope & Requirements Proposal")
r.font.size = Pt(18)
r.font.color.rgb = ACCENT

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("AI-First Vehicle Acquisition Platform for Automotive Dealerships")
r.font.size = Pt(12)
r.font.italic = True
r.font.color.rgb = GREY

for _ in range(6):
    doc.add_paragraph()

# Cover meta table
meta = doc.add_table(rows=5, cols=2)
meta.alignment = WD_TABLE_ALIGNMENT.CENTER
meta_data = [
    ("Prepared for", "Renaud & Yves"),
    ("Prepared by", "Development Team \u2014 AutoNova AI"),
    ("Document", "Scope, Deliverables, Timeline & Commercial Terms"),
    ("Date", "June 2026"),
    ("Status", "Confidential \u2014 For Review"),
]
meta.columns[0].width = Inches(1.9)
meta.columns[1].width = Inches(3.8)
for i, (k, v) in enumerate(meta_data):
    c0 = meta.cell(i, 0)
    c1 = meta.cell(i, 1)
    c0.width = Inches(1.9)
    c1.width = Inches(3.8)
    r0 = c0.paragraphs[0].add_run(k)
    r0.font.bold = True
    r0.font.size = Pt(10)
    r0.font.color.rgb = WHITE
    set_cell_bg(c0, "0F172A")
    r1 = c1.paragraphs[0].add_run(v)
    r1.font.size = Pt(10)
    r1.font.color.rgb = INK
    set_cell_bg(c1, "EEF3FF")

doc.add_page_break()

# =========================================================================
# 1. EXECUTIVE SUMMARY
# =========================================================================
add_heading("1.  Executive Summary")
add_body(
    "This document has been prepared in response to your request to review the AutoNova AI project "
    "and to establish a clear, mutually agreed scope, timeline, and commercial arrangement for its final "
    "delivery. It consolidates the current status of the platform, the work remaining to reach a fully "
    "functional production release, the information required from participating dealerships, and the terms "
    "under which the intellectual property and complete source code will be transferred upon full payment."
)
add_body(
    "AutoNova AI is an AI-first SaaS platform that qualifies private vehicle sellers into dealership "
    "appointments through an automated conversational interface, applies deterministic business logic for "
    "lead scoring and inventory matching, and equips dealership staff with a management dashboard for leads, "
    "inventory, and appointments. The platform is already live in an MVP capacity and is now being scoped for "
    "completion, hardening, and full commercial rollout."
)
add_body(
    "The intent of this proposal is to give you and Yves a single, transparent reference to review the project "
    "end-to-end, confirm the remaining scope in writing, and move forward on a fixed-price basis for the final "
    "delivery, as requested."
)

# =========================================================================
# 2. UNDERSTANDING OF YOUR REQUIREMENTS
# =========================================================================
add_heading("2.  Understanding of Your Requirements")
add_body(
    "Based on our recent discussions, the following points capture what you and Yves have asked us to address. "
    "We restate them here to confirm a shared understanding before proceeding to the final stage."
)
add_bullet("A complete review of the current project status, including the code repository and what has been built to date.", bold_prefix="Project review \u2014 ")
add_bullet("A clear breakdown of what remains to be completed to reach a fully functional application.", bold_prefix="Remaining work \u2014 ")
add_bullet("A precise definition of what \u201cfully functional\u201d includes so scope is not left open to interpretation.", bold_prefix="Scope definition \u2014 ")
add_bullet("A realistic estimate for completing the remaining work, understood to be in the region of one month.", bold_prefix="Timeline \u2014 ")
add_bullet("A transition from a commission-based arrangement to an agreed fixed price for the final delivery.", bold_prefix="Commercial model \u2014 ")
add_bullet("Confirmation that the complete source code and intellectual property will be transferred after full payment.", bold_prefix="IP & handover \u2014 ")
add_bullet("All terms confirmed in writing before the final stage, followed by a joint review meeting with Yves.", bold_prefix="Written confirmation \u2014 ")

# =========================================================================
# 3. CURRENT PROJECT STATUS
# =========================================================================
add_heading("3.  Current Project Status")
add_body(
    "The platform is operational as a deployed MVP. The core acquisition flow \u2014 from a private seller's first "
    "message through to a booked dealership appointment \u2014 is functional end-to-end. The items below reflect what "
    "has been completed and what remains."
)

add_subheading("3.1  Completed to date")
completed = [
    "Public-facing AI conversational interface that extracts structured vehicle and seller information and detects intent.",
    "Deterministic business logic engine for lead scoring, qualification thresholds, and financing estimation.",
    "Inventory matching that pairs qualified sellers with relevant dealership stock.",
    "Appointment booking flow generated from qualified, high-intent leads.",
    "Dealership employee dashboard for lead management, inventory, and appointments.",
    "Multi-tenant architecture supporting multiple dealership organisations, user roles, and authentication.",
    "Native Google sign-in (Google Identity Services) and email/password authentication.",
    "Admin onboarding wizard for configuring a new dealership organisation.",
    "Responsive, dark-themed public landing page under the autonovaia.ca brand.",
    "Direct integration with the Google Gemini AI model for the conversational engine.",
    "Live deployment on cloud hosting with a managed MongoDB database.",
    "Performance-optimised dashboard and leads queries.",
]
for c in completed:
    add_bullet(c)

add_subheading("3.2  Remaining to reach full production release")
remaining = [
    "Dealership inventory onboarding \u2014 structured import and ongoing update of live inventory (including CSV import and, where available, DMS/inventory feed synchronisation).",
    "AI tuning \u2014 refining the conversational model's behaviour, prompts, and qualification accuracy against real dealership data.",
    "Geolocation sync \u2014 mapping each dealership's identity, address/GPS, hours, branding, and contact details into the platform.",
    "Live notifications \u2014 replacing simulated email/SMS logs with real appointment confirmations and hot-lead alerts.",
    "Human takeover \u2014 allowing dealership staff to pause the AI, message a seller directly, and reassign lead ownership.",
    "Production hardening \u2014 final security review, error handling, monitoring, and documentation.",
]
for r_item in remaining:
    add_bullet(r_item)

# =========================================================================
# 4. FULLY FUNCTIONAL APPLICATION - SCOPE
# =========================================================================
add_heading("4.  Definition of the Fully Functional Application")
add_body(
    "For the avoidance of doubt, the \u201cfully functional application\u201d delivered at the end of this engagement "
    "will comprise the following capabilities. Anything outside this list is considered a future enhancement and "
    "would be scoped separately."
)

scope_table = doc.add_table(rows=1, cols=2)
scope_table.style = "Light Grid Accent 1"
hdr = scope_table.rows[0].cells
for cell, text in zip(hdr, ("Module", "Included Capability")):
    set_cell_bg(cell, "0F172A")
    run = cell.paragraphs[0].add_run(text)
    run.font.bold = True
    run.font.color.rgb = WHITE
    run.font.size = Pt(10)

scope_rows = [
    ("Seller AI Chat", "Public conversational assistant that qualifies private sellers, captures vehicle and contact data, and detects buying/selling intent."),
    ("Lead Scoring & Qualification", "Deterministic scoring, qualification thresholds, and financing estimation applied consistently to every lead."),
    ("Inventory Management", "Add, edit, and import dealership inventory (manual + CSV), with matching against qualified sellers."),
    ("Appointment Booking", "Automated appointment creation from qualified leads, visible and manageable by staff."),
    ("Dealership Dashboard", "Lead pipeline, inventory view, appointment calendar, and organisation settings for each dealership."),
    ("Human Takeover", "Staff can pause the AI, take over the conversation manually, and reassign lead ownership."),
    ("Notifications", "Real email/SMS confirmations for appointments and instant alerts for high-value leads."),
    ("Multi-Tenant & Roles", "Isolated data per dealership, role-based access, and secure authentication."),
    ("Geolocation & Branding", "Per-dealership identity, address/GPS, hours, contact, and logo applied across the experience."),
]
for module, capability in scope_rows:
    cells = scope_table.add_row().cells
    rc = cells[0].paragraphs[0].add_run(module)
    rc.font.bold = True
    rc.font.size = Pt(10)
    rc.font.color.rgb = INK
    cc = cells[1].paragraphs[0].add_run(capability)
    cc.font.size = Pt(10)

# =========================================================================
# 5. DEALERSHIP DATA REQUIREMENTS
# =========================================================================
add_heading("5.  Dealership Onboarding & Data Requirements")
add_body(
    "To activate each dealership on the platform and to power the geolocation sync, branding, and inventory "
    "matching features, the following information is required per dealership. The set you proposed is sufficient "
    "to build the geolocation sync; we have organised it below and noted the purpose of each item."
)

data_table = doc.add_table(rows=1, cols=2)
data_table.style = "Light Grid Accent 1"
hdr = data_table.rows[0].cells
for cell, text in zip(hdr, ("Information Required", "Purpose")):
    set_cell_bg(cell, "0F172A")
    run = cell.paragraphs[0].add_run(text)
    run.font.bold = True
    run.font.color.rgb = WHITE
    run.font.size = Pt(10)

data_rows = [
    ("Legal & trading identity", "Uniquely identify the dealership organisation within the platform."),
    ("Address / GPS coordinates", "Power geolocation sync and match sellers to the nearest location."),
    ("Branding assets", "Apply dealership colours and visual identity to the seller experience."),
    ("Business hours", "Offer valid appointment slots and set seller expectations."),
    ("Contact details", "Route notifications and enable staff follow-up."),
    ("DMS / inventory feed access", "Synchronise live inventory automatically where a feed is available."),
    ("Logo usage authorisation", "Legally display the dealership logo across public-facing surfaces."),
]
for info, purpose in data_rows:
    cells = data_table.add_row().cells
    rc = cells[0].paragraphs[0].add_run(info)
    rc.font.bold = True
    rc.font.size = Pt(10)
    rc.font.color.rgb = INK
    cc = cells[1].paragraphs[0].add_run(purpose)
    cc.font.size = Pt(10)

add_body("")
add_body(
    "Confirmation: the list above is sufficient to build the geolocation sync feature. Should any additional "
    "field be needed during implementation, we will flag it promptly.", space_after=4
)

# =========================================================================
# 6. TECHNICAL ARCHITECTURE
# =========================================================================
add_heading("6.  Technical Architecture Overview")
add_body(
    "The platform is built on a modern, maintainable stack chosen for reliability and ease of future development."
)
add_bullet("A single-page web application built with React and a component-based UI system.", bold_prefix="Front end \u2014 ")
add_bullet("A Python (FastAPI) service exposing a secured REST API and hosting the business logic engine.", bold_prefix="Back end \u2014 ")
add_bullet("A managed MongoDB database with multi-tenant data isolation per dealership.", bold_prefix="Database \u2014 ")
add_bullet("Google Gemini for the conversational engine and Google Identity Services for authentication.", bold_prefix="Integrations \u2014 ")
add_bullet("Cloud-hosted web services with environment-based configuration and a documented deployment blueprint.", bold_prefix="Hosting \u2014 ")

# =========================================================================
# 7. TIMELINE
# =========================================================================
add_heading("7.  Estimated Timeline")
add_body(
    "The remaining work is estimated at approximately four weeks of focused development, subject to timely "
    "delivery of dealership data and access. The indicative phasing is as follows."
)

tl_table = doc.add_table(rows=1, cols=3)
tl_table.style = "Light Grid Accent 1"
hdr = tl_table.rows[0].cells
for cell, text in zip(hdr, ("Phase", "Focus", "Indicative Duration")):
    set_cell_bg(cell, "0F172A")
    run = cell.paragraphs[0].add_run(text)
    run.font.bold = True
    run.font.color.rgb = WHITE
    run.font.size = Pt(10)

tl_rows = [
    ("Week 1", "Inventory onboarding (manual + CSV) and dealership geolocation/branding sync.", "~1 week"),
    ("Week 2", "AI tuning against real data; qualification accuracy improvements.", "~1 week"),
    ("Week 3", "Human takeover and live email/SMS notifications.", "~1 week"),
    ("Week 4", "Production hardening, security review, documentation, and handover preparation.", "~1 week"),
]
for phase, focus, dur in tl_rows:
    cells = tl_table.add_row().cells
    r0 = cells[0].paragraphs[0].add_run(phase)
    r0.font.bold = True
    r0.font.size = Pt(10)
    r0.font.color.rgb = INK
    cells[1].paragraphs[0].add_run(focus).font.size = Pt(10)
    cells[2].paragraphs[0].add_run(dur).font.size = Pt(10)

add_body("")
add_body(
    "Note: the timeline assumes dealership information and any DMS/feed access are provided at the start of the "
    "engagement. Delays in receiving this data may shift the schedule accordingly.", space_after=4
)

# =========================================================================
# 8. COMMERCIAL TERMS
# =========================================================================
add_heading("8.  Commercial Terms")
add_body(
    "In line with your preference, we are open to moving from a commission-based arrangement to a single agreed "
    "fixed price for the final delivery. This provides cost certainty for you and a clearly bounded scope for us."
)
add_bullet("A fixed price covering the remaining scope defined in Sections 3.2 and 4, to be agreed jointly.", bold_prefix="Fixed fee \u2014 ")
add_bullet("A proposed structure of an initial deposit to commence work and the balance on final delivery, prior to source-code transfer.", bold_prefix="Payment schedule \u2014 ")
add_bullet("Any capability outside Section 4 is treated as a change request and quoted separately before work begins.", bold_prefix="Out of scope \u2014 ")
add_body(
    "The specific figures and payment milestones will be confirmed together with Yves during the review meeting "
    "and recorded in the written agreement.", space_after=4
)

# =========================================================================
# 9. IP & SOURCE CODE TRANSFER
# =========================================================================
add_heading("9.  Intellectual Property & Source-Code Transfer")
add_body(
    "We confirm and fully respect the following, which will be recorded in the written agreement:"
)
add_bullet("The source code and intellectual property remain with the development team until the mutually agreed amount is paid in full.", bold_prefix="Retention \u2014 ")
add_bullet("Upon completion of full payment, complete ownership of the AutoNova AI source code and intellectual property transfers to you.", bold_prefix="Transfer on payment \u2014 ")
add_bullet("No partial release of the source code will occur before full payment; interim reviews are conducted via live walkthrough with Yves.", bold_prefix="No early release \u2014 ")

# =========================================================================
# 10. HANDOVER PACKAGE
# =========================================================================
add_heading("10.  Final Handover Package")
add_body(
    "On full payment, you will receive everything required to maintain and develop the application independently:"
)
handover = [
    "Complete source code and repository (front end and back end).",
    "Back-end services and business-logic engine.",
    "Database structure and schema documentation.",
    "All API and AI integration configurations.",
    "Deployment configuration and hosting blueprint.",
    "Technical and operational documentation.",
    "All project access and credentials required for ongoing maintenance and future development.",
]
for h in handover:
    add_bullet(h)

# =========================================================================
# 11. NEXT STEPS
# =========================================================================
add_heading("11.  Next Steps")
add_bullet("Review this document with Yves and confirm the scope in Sections 3.2, 4, and 5.", bold_prefix="1.  ")
add_bullet("Agree the fixed price and payment schedule (Section 8).", bold_prefix="2.  ")
add_bullet("Record the agreed terms, IP transfer, and handover in writing before the final stage.", bold_prefix="3.  ")
add_bullet("Schedule the joint review meeting for a live walkthrough of the platform.", bold_prefix="4.  ")
add_bullet("Provide the dealership data and any DMS/feed access so remaining work can begin without delay.", bold_prefix="5.  ")

doc.add_paragraph()
closing = doc.add_paragraph()
r = closing.add_run(
    "We are confident the remaining work can be completed efficiently and delivered as a fully functional, "
    "production-ready platform. We look forward to reviewing everything with you and Yves and to formalising "
    "the final stage of the AutoNova AI project."
)
r.font.italic = True
r.font.color.rgb = GREY
r.font.size = Pt(10.5)

# Footer
section = doc.sections[0]
footer = section.footer
fp = footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fr = fp.add_run("AutoNova AI  \u2022  Project Scope & Requirements Proposal  \u2022  Confidential")
fr.font.size = Pt(8)
fr.font.color.rgb = LIGHT

out = "/app/frontend/public/AutoNova_AI_Project_Scope_Proposal.docx"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
doc.save(out)
print("Saved:", out)
