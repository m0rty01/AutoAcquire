from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem

OUT = "/app/frontend/public/AutoNova_AI_Development_Progress_Report.pdf"
NAVY = colors.HexColor("#0B1F3A")
ACCENT = colors.HexColor("#2563EB")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=NAVY, spaceAfter=6)
SUB = ParagraphStyle("SUB", parent=ss["Normal"], fontSize=11, textColor=colors.HexColor("#475569"), spaceAfter=18)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=14, textColor=NAVY, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontSize=10, leading=14.5)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.5, textColor=colors.HexColor("#64748B"))


def bullets(items):
    return ListFlowable([ListItem(Paragraph(i, BODY), leftIndent=12) for i in items], bulletType="bullet", start="•", leftIndent=14)


def table(rows, widths):
    t = Table([[Paragraph(str(c), BODY if i else ParagraphStyle("th", parent=BODY, textColor=colors.white, fontName="Helvetica-Bold")) for c in r]
               for i, r in enumerate(rows)], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(0.75 * inch, 0.5 * inch, "AutoNova AI — Development Progress Report — Confidential")
    canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


MILESTONES = [
    ("Milestone 1A — Customer Profile (10 tabs)", [
        "Full customer profile page that opens when you click a lead on the Kanban pipeline (also linked from the lead workspace).",
        "<b>Overview</b>: name, email, phone, preferred language, creation date, source, score, assigned dealership and representative, pipeline stage, last interaction, next follow-up, status.",
        "<b>Vehicle Preferences</b>: type, make/model, year, budget, mileage, transmission, fuel, financing, trade-in details, plus recommended and matched vehicles.",
        "<b>Conversation History</b>: complete AI conversation with timestamps, language, customer questions, AI answers and vehicle recommendations.",
        "<b>Activities</b>: the existing chronological timeline (creation, assignment, stage changes, consent, appointments, communications, test drives, sales, notes).",
        "<b>Appointments, Test Drives, Referrals, Sales</b>: every record with status, dates, dealership and representative; sale amounts and commissions shown only to authorized roles.",
        "<b>Communications</b>: email/SMS history with delivery status, a send panel using approved templates, and communication preferences.",
        "<b>Consent &amp; Privacy</b>: read-only consent records (version, language, timestamp, recipients, data shared), permission history and consent withdrawal recorded as a new entry — historical records are never modified.",
        "Profile actions: assign/reassign, change stage (with lost reason), schedule and complete follow-ups, add internal notes, edit customer details — all logged in the activity timeline.",
    ]),
    ("Milestone 1B — User Management", [
        "New User Management section: list, search, filter by role, status, dealer group and dealership.",
        "Create users with a secure one-time setup link (no one ever chooses or sees another person's password).",
        "Edit details, change roles, assign dealership and dealer group, deactivate and reactivate accounts, initiate secure password resets, see last login and account status.",
        "Roles: Super Admin, Platform Support / Operations, Dealership Admin, Dealership Manager, Sales Representative.",
        "Permissions enforced on the server: managers can only manage sales representatives; nobody can grant platform-wide privileges except Super Admin; users cannot change their own role or deactivate themselves.",
        "Deactivated users are blocked immediately (login and existing sessions). New “Choose your password” page for setup and reset links.",
    ]),
    ("Milestone 2A/2B — Email (Resend) and SMS (Twilio)", [
        "Real Resend email integration using the client's own key, sender <b>Support &lt;support@autonovaia.ca&gt;</b>.",
        "Twilio SMS integration built and ready; it activates as soon as the Twilio keys and sending number are added.",
        "Bilingual (English / French) server-side templates: appointment confirmation and reminder, test-drive confirmation and reminder, follow-up, dealership referral notification, staff alerts, user invitation, password reset.",
        "Delivery tracking: queued, sent, delivered, bounced, failed, undelivered — with provider message IDs, timestamps and full event history.",
        "Secure provider webhooks with signature verification (Resend and Twilio), duplicate-event protection, inbound SMS replies and STOP/ARRÊT opt-out handling.",
        "Duplicate-message prevention, honest statuses (“Not Configured” / “Blocked”) when a provider or permission is missing, and one-click retry.",
        "Separate communication permissions per customer: operational, appointment-related and promotional. Referral consent never implies marketing permission.",
        "New <b>Communication Center</b>: every email and SMS with customer, representative, status, filters and retry.",
    ]),
    ("Milestone 2C — Automated Follow-up Engine", [
        "Workflow A — New consented lead: CRM stage update, dealership notification, automatic representative assignment (least-busy or chosen rep), delivery record, follow-up task.",
        "Workflow B — Uncontacted lead: alert the representative, create an overdue task, escalate to managers after a configurable time.",
        "Workflow C — Appointment confirmed: customer confirmation (email/SMS) and automatic reminder.",
        "Workflow D — Test drive confirmed: confirmation, reminder and representative notification.",
        "Workflow E — Inactive customer: follow-up task, optional approved message only if permission exists.",
        "Administration page: enable/disable, delays, template, language, channels, assignee, thresholds, execution history, error log and retry.",
        "Runs every 15 minutes on a schedule; idempotent (no duplicates) and loop-safe; reminders cancel automatically when an appointment or test drive is cancelled or rescheduled.",
    ]),
    ("Milestone 3 — Test Drive Management", [
        "Dedicated Test Drives section built on the existing appointment infrastructure (appointments never become test drives automatically).",
        "Each record: customer, referral, dealership, vehicle, representative, requested and confirmed times, status, notes, feedback, completion time.",
        "Statuses: Requested, Pending Confirmation, Confirmed, Completed, Cancelled, Customer No-Show, Dealership Declined — with enforced transitions.",
        "Actions: create, confirm, decline, reschedule, cancel, complete with customer feedback, no-show, notes, link to a vehicle sale.",
        "Dashboard: total, upcoming, completed, cancelled, no-shows and test-drive-to-sale conversion rate, filterable by dealership, representative and date range.",
    ]),
    ("Milestone 4 — Commission Enhancements", [
        "Versioned commission agreements per dealer group with full history and effective dates.",
        "Volume-based tiers: thresholds, amount per sale and/or percentage, monthly or quarterly period.",
        "Incremental and retroactive calculation methods, clearly displayed. Retroactive uplifts are added as separate adjustment lines — previously generated commissions are never changed.",
        "Commission ledger with filters (date, dealer group, commission status, sale status) and <b>CSV and PDF export</b>.",
        "Financial data restricted to authorized roles; double verification and double rejection blocked.",
    ]),
    ("Milestone 5 — External Inventory Integrations (architecture)", [
        "Inventory Integrations page for Le Don de L'Auto, Le Prix du Gros and H. Grégoire — each marked <b>Pending Credentials</b> until official documentation and access are supplied.",
        "Independent adapters (H. Grégoire does not assume the same format as the others), normalization of all required vehicle fields, sold and removed vehicle detection, duplicate detection, sync logs and error reporting.",
        "External vehicle ID mapping scoped by source and dealership (inventory codes are not treated as globally unique), VIN-assisted matching.",
        "Le Don de L'Auto ↔ Le Prix du Gros code mapping with history, conflict detection and manual review — conflicting mappings are never overwritten silently.",
        "Sandbox mode with clearly labelled SAMPLE data to demonstrate the pipeline; sample vehicles are never shown to customers.",
    ]),
    ("Milestone 6 — French Administrative Localization (first phase)", [
        "Global EN/FR switcher in the header; preference saved per user and restored at login.",
        "French-Canadian labels for navigation, page titles, customer profile, statuses, tables, user management, communications, automations, test drives, sales and integrations.",
        "Localized dates and Canadian dollar formatting (fr-CA / en-CA).",
    ]),
    ("Milestone 7 — Security, Privacy and Reliability", [
        "Protection against password guessing (failed-login limits), limits on password-reset requests and on public chat messages.",
        "Strict data isolation: sales representatives only see customers, appointments, referrals and sales assigned to them.",
        "System Health page: database, email/SMS providers, 24-hour delivery failures, background jobs and inventory sync status; public health-check endpoint for uptime monitoring.",
        "Dealer groups are archived instead of deleted to preserve referral, sale and commission history.",
        "Backup and recovery procedures documented for the production database.",
    ]),
]

PENDING = [
    ["Item", "What is needed", "Owner"],
    ["Real email delivery", "Verify the autonovaia.ca domain in Resend (DNS records) and confirm the webhook signing secret (starts with “whsec_”).", "Client"],
    ["SMS delivery", "Twilio Account SID, Auth Token and sending phone number.", "Client"],
    ["Partner inventory", "Official API/feed documentation, credentials and data-use permission from Le Don de L'Auto, Le Prix du Gros and H. Grégoire.", "Client / partners"],
    ["French coverage", "Remaining screens (Leads list, lead workspace, Dashboard, Inventory, Partners, Settings) still to translate.", "Development"],
    ["Legal review", "Qualified review of consent wording for Law 25, PIPEDA and Canadian anti-spam rules. No compliance is claimed until reviewed.", "Client / legal"],
    ["Production release", "Save to GitHub and redeploy on Render so autonovaia.ca receives today's work.", "Client"],
]


def build():
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.8 * inch,
                            title="AutoNova AI — Development Progress Report")
    s = [Paragraph("AutoNova AI", H1), Paragraph("Development Progress Report — CRM, Communications, Test Drives, Commissions, Integrations and Production Readiness", SUB)]
    s.append(Paragraph("Executive Summary", H2))
    s.append(Paragraph(
        "Today's work completed the remaining development plan for AutoNova AI in the agreed order — Milestones 1 through 7 — by extending the existing "
        "platform rather than rebuilding it. Every previously delivered feature (AI assistant, consent gating, referrals, appointments, sales verification, "
        "commissions and the Kanban pipeline) was preserved. Each milestone was tested end-to-end with automated backend and browser tests across three test "
        "rounds; all issues found were corrected and re-verified.", BODY))
    s.append(Spacer(1, 10))
    s.append(table([["Milestone", "Scope", "Status"],
                    ["1A", "Customer Profile — 10 tabs + actions", "Completed & tested"],
                    ["1B", "User Management interface", "Completed & tested"],
                    ["2A", "Email (Resend)", "Integrated — awaiting domain verification"],
                    ["2B", "SMS (Twilio)", "Integrated — awaiting credentials"],
                    ["2C", "Automated follow-up engine (Workflows A–E)", "Completed & tested"],
                    ["3", "Test Drive Management", "Completed & tested"],
                    ["4", "Volume tiers + CSV/PDF commission exports", "Completed & tested"],
                    ["5", "Partner inventory integrations", "Architecture complete — pending partner credentials"],
                    ["6", "French administrative localization", "First phase completed"],
                    ["7", "Privacy, security, monitoring", "Completed & tested"]], [0.8 * inch, 3.6 * inch, 2.6 * inch]))
    s.append(PageBreak())
    s.append(Paragraph("Functionality Delivered", H2))
    for title, items in MILESTONES:
        s.append(Paragraph(title, H3))
        s.append(bullets(items))
    s.append(Paragraph("Testing &amp; Verification", H2))
    s.append(bullets([
        "Three full automated test rounds (backend API and browser flows); all reported issues fixed and re-verified.",
        "Live Resend check: a test email was sent through the client's account and its delivery status updated to “Delivered” via a signed webhook; an invalid signature was correctly rejected.",
        "Regression checks confirmed the AI chat, consent flow, appointments, pipeline, sales verification and existing commissions still work.",
    ]))
    s.append(Paragraph("Outstanding Items &amp; Next Steps", H2))
    s.append(table(PENDING, [1.4 * inch, 4.3 * inch, 1.3 * inch]))
    s.append(Spacer(1, 14))
    s.append(Paragraph("Integrations that depend on third-party credentials or partner documentation are built and ready, and are clearly labelled in the "
                       "application until they are activated. No partner endpoints, credentials or data were invented.", SMALL))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    build()
    print(OUT)
