"""Customer-safe document presentation. Authorization stays in domain services/views."""

from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings


def estimate_token(estimate, *, actor):
    from operations.services import create_access_token

    return create_access_token(actor=actor, obj=estimate, purpose="estimate")


def invoice_token(invoice, *, actor):
    from operations.services import create_access_token

    return create_access_token(actor=actor, obj=invoice, purpose="invoice")


def document_pdf(document, *, kind):
    """Never include model reprs, compensation fields, or internal notes in PDFs."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodySafe", fontName="Helvetica", fontSize=10, leading=15, textColor=colors.HexColor("#34434b")
        )
    )
    styles.add(ParagraphStyle(name="SmallSafe", parent=styles["BodySafe"], fontSize=8, leading=12))
    styles.add(ParagraphStyle(name="RightSafe", parent=styles["BodySafe"], alignment=TA_RIGHT))
    styles.add(
        ParagraphStyle(name="TotalSafe", parent=styles["RightSafe"], fontName="Helvetica-Bold", fontSize=17, leading=22)
    )
    styles["Title"].textColor = colors.HexColor("#122f3a")
    styles["Title"].fontName = "Helvetica-Bold"

    def p(value, style="BodySafe"):
        return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), styles[style])

    def money(value):
        return f"${value:,.2f}"

    number = document.number or "Draft"
    pdf = SimpleDocTemplate(
        stream,
        pagesize=(612, 792),
        rightMargin=46,
        leftMargin=46,
        topMargin=42,
        bottomMargin=52,
        title=f"FirstGlanceKnox {kind} {number}",
        author="FirstGlanceKnox",
    )
    brand = settings.BASE_DIR / "static" / "brand" / "logo.jpg"
    brand_content = Image(str(brand), width=64, height=64) if brand.exists() else p("FirstGlanceKnox")
    heading = Table([[brand_content, p(f"FIRSTGLANCEKNOX\n{kind.upper()} {number}", "RightSafe")]], colWidths=[80, 440])
    heading.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#03a7fc")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
            ]
        )
    )
    content = [heading, Spacer(1, 22), p("A clear view. A clear breakdown.", "Title"), Spacer(1, 14)]
    billing = getattr(document, "billing_snapshot", {}) or {}
    customer_name = billing.get("name", document.customer.name)
    property_obj = document.property if kind == "estimate" else document.job.property
    content += [p(customer_name), p(property_obj.address), Spacer(1, 12)]
    if kind == "invoice":
        content += [
            p(
                f"Issued: {document.issued_at.strftime('%b %d, %Y') if document.issued_at else 'Draft'}  |  Due: {document.due_date.strftime('%b %d, %Y')}"
            ),
            p(f"Status: {document.get_status_display()}"),
        ]
        if document.purchase_order:
            content += [p(f"Purchase order: {document.purchase_order}")]
    else:
        content += [p(f"Status: {document.get_status_display()}")]
        if document.expires_on:
            content += [p(f"Valid through: {document.expires_on.strftime('%b %d, %Y')}")]
    content += [Spacer(1, 20)]
    rows = [[p("SERVICE", "SmallSafe"), p("QTY", "SmallSafe"), p("RATE", "SmallSafe"), p("AMOUNT", "SmallSafe")]]
    for line in document.lines.all():
        rows.append(
            [
                p(line.description),
                p(f"{line.quantity:g} {line.unit}", "SmallSafe"),
                p(money(line.unit_price), "RightSafe"),
                p(money(line.total), "RightSafe"),
            ]
        )
    table = Table(rows, colWidths=[252, 92, 82, 94], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf5f8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#dce5e9")),
            ]
        )
    )
    content.extend([table, Spacer(1, 14)])
    totals = [
        [p("Subtotal"), p(money(document.subtotal), "RightSafe")],
        [p("Discount"), p("-" + money(document.discount), "RightSafe")],
        [p("Tax"), p(money(document.tax), "RightSafe")],
        [p("Total"), p(money(document.total), "TotalSafe")],
    ]
    if kind == "invoice":
        totals += [
            [p("Payments recorded"), p(money(document.paid_amount), "RightSafe")],
            [p("Balance due"), p(money(document.balance), "TotalSafe")],
        ]
    total_table = Table(totals, colWidths=[360, 160])
    total_table.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    content += [total_table, Spacer(1, 22)]
    if document.terms:
        content += [p("TERMS", "SmallSafe"), Spacer(1, 5), p(document.terms), Spacer(1, 15)]
    if kind == "estimate":
        if document.customer_notes:
            content += [p(document.customer_notes), Spacer(1, 12)]
        if document.accepted_at:
            content += [p(f"Approved by {document.accepted_by} on {document.accepted_at.strftime('%b %d, %Y')}.")]
    else:
        content += [p("PAYMENT DETAILS", "SmallSafe"), Spacer(1, 5), p(settings.PAYMENT_INSTRUCTIONS)]
        if document.status == "void":
            content += [Spacer(1, 12), p("This invoice is void. No payment is requested.")]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dce5e9"))
        canvas.line(46, 39, 566, 39)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#566870"))
        canvas.drawString(46, 25, "FirstGlanceKnox  |  Knoxville area")
        canvas.drawRightString(566, 25, f"{number}  |  Page {doc.page}")
        canvas.restoreState()

    pdf.build(content, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def estimate_pdf(estimate):
    return document_pdf(estimate, kind="estimate")


def invoice_pdf(invoice):
    return document_pdf(invoice, kind="invoice")
