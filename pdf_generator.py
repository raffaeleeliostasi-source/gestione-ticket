# ============================================================
# PDF GENERATOR — GESTIONE TICKET
# Versione completa: ticket + foto + storico interventi + firme
# ============================================================

from io import BytesIO
from html import escape
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether

try:
    from PIL import Image as PILImage
except Exception:
    PILImage = None

import database as db

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
LIGHT_BLUE = colors.HexColor("#EAF3FB")
VERY_LIGHT = colors.HexColor("#F6F8FA")
BORDER = colors.HexColor("#D5DDE5")
TEXT = colors.HexColor("#263238")
MUTED = colors.HexColor("#66727D")
WHITE = colors.white
GREEN = colors.HexColor("#15803D")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B91C1C")

PRIORITY_COLORS = {
    "bassa": GREEN,
    "media": colors.HexColor("#CA8A04"),
    "alta": colors.HexColor("#EA580C"),
    "urgente": RED,
}

_styles = getSampleStyleSheet()
STYLES = {
    "header": ParagraphStyle("Header", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=17, leading=19, textColor=WHITE, alignment=TA_LEFT),
    "header_right": ParagraphStyle("HeaderRight", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=WHITE, alignment=TA_CENTER),
    "title": ParagraphStyle("Title", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=TA_LEFT),
    "section": ParagraphStyle("Section", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=WHITE, alignment=TA_LEFT),
    "label": ParagraphStyle("Label", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=MUTED),
    "value": ParagraphStyle("Value", parent=_styles["Normal"], fontName="Helvetica", fontSize=9, leading=11, textColor=TEXT),
    "box_title": ParagraphStyle("BoxTitle", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=NAVY),
    "box_text": ParagraphStyle("BoxText", parent=_styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT),
    "small": ParagraphStyle("Small", parent=_styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9, textColor=MUTED),
    "signature": ParagraphStyle("Signature", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER),
    "intervention_title": ParagraphStyle("InterventionTitle", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=NAVY),
}


def _txt(value):
    if value is None:
        return ""
    return escape(str(value)).replace("\n", "<br/>")


def _first(item, *keys):
    if not isinstance(item, dict):
        return ""
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return ""


def _format_date(value):
    if value in (None, ""):
        return ""
    try:
        return db.format_data(value)
    except Exception:
        pass
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _section_header(title):
    table = Table([[Paragraph(_txt(title), STYLES["section"])]], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _info_table(rows):
    data = []
    for i in range(0, len(rows), 2):
        row = [Paragraph(_txt(rows[i][0]), STYLES["label"]), Paragraph(_txt(rows[i][1]), STYLES["value"])]
        if i + 1 < len(rows):
            row += [Paragraph(_txt(rows[i + 1][0]), STYLES["label"]), Paragraph(_txt(rows[i + 1][1]), STYLES["value"])]
        else:
            row += ["", ""]
        data.append(row)
    table = Table(data, colWidths=[43 * mm, 44 * mm, 43 * mm, 44 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _text_box(title, text):
    table = Table([
        [Paragraph(_txt(title), STYLES["box_title"])],
        [Paragraph(_txt(text or "—"), STYLES["box_text"])],
    ], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("BACKGROUND", (0, 1), (-1, 1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _priority_badge(priority):
    value = str(priority or "—")
    bg = PRIORITY_COLORS.get(value.strip().lower(), BLUE)
    table = Table([[Paragraph(_txt(value), ParagraphStyle("Priority", parent=STYLES["value"], fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER))]], colWidths=[34 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, bg),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _image_from_bytes(raw, max_width=145 * mm, max_height=82 * mm):
    if not raw:
        return None
    try:
        if PILImage is not None:
            pil = PILImage.open(BytesIO(raw))
            if pil.mode not in ("RGB", "RGBA"):
                pil = pil.convert("RGB")
            out = BytesIO()
            pil.save(out, format="PNG" if pil.mode == "RGBA" else "JPEG")
            out.seek(0)
            image = RLImage(out)
        else:
            image = RLImage(BytesIO(raw))
        iw, ih = image.imageWidth, image.imageHeight
        if not iw or not ih:
            return None
        scale = min(max_width / iw, max_height / ih, 1.0)
        image.drawWidth = iw * scale
        image.drawHeight = ih * scale
        image.hAlign = "CENTER"
        return image
    except Exception:
        return None


def _get_attachments(ticket_id):
    try:
        return db.get_allegati(ticket_id) or []
    except Exception:
        return []


def _get_interventions(ticket_id):
    try:
        return db.get_interventi(ticket_id) or []
    except Exception:
        # Compatibilità con versioni precedenti del database.py
        try:
            last = db.get_intervento(ticket_id)
            return [last] if last else []
        except Exception:
            return []


def _draw_footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 12 * mm, width - 18 * mm, 12 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 7.5 * mm, "Gestione Ticket — Report Ufficiale")
    canvas.drawRightString(width - 18 * mm, 7.5 * mm, f"Pagina {doc.page}")
    canvas.restoreState()



def _scarica_firma(path, amministratore=False):
    """Recupera la firma tramite gli helper del database."""
    if not path:
        return None
    try:
        if amministratore:
            return db.scarica_firma_amministratore(path)
        return db.scarica_firma_intervento(path)
    except Exception:
        return None


def _signature_box(title, raw_signature, width=174 * mm):
    image = _image_from_bytes(raw_signature, max_width=58 * mm, max_height=25 * mm)
    content = [[Paragraph(_txt(title), STYLES["signature"])]]
    if image:
        content.append([image])
    else:
        content.append([Spacer(1, 14 * mm)])
        content.append([Paragraph("Firma non disponibile", STYLES["small"])])
    table = Table(content, colWidths=[width])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def genera_pdf(ticket):
    if not ticket:
        raise ValueError("Ticket non valido.")

    ticket_id = _first(ticket, "id")
    titolo = _first(ticket, "titolo", "title")
    stato = _first(ticket, "stato", "status")
    priorita = _first(ticket, "priorita", "priorità", "priority")
    categoria = _first(ticket, "categoria", "category")
    creato_da = _first(ticket, "creato_da", "created_by")
    assegnato_a = _first(ticket, "assegnato_a", "assegnato", "assigned_to")
    data_creazione = _first(ticket, "creato_il", "created_at", "data_creazione", "created_on")
    data_chiusura = _first(ticket, "data_chiusura", "chiuso_il", "closed_at", "closed_on")
    chiuso_da = _first(ticket, "chiuso_da", "closed_by")
    descrizione = _first(ticket, "descrizione", "description")

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Ticket #{ticket_id}", author="Gestione Ticket",
    )
    story = []

    # TESTATA
    header = Table([[Paragraph("GESTIONE TICKET", STYLES["header"]), Paragraph(f"TICKET #{_txt(ticket_id)}", STYLES["header_right"])]], colWidths=[116 * mm, 58 * mm], rowHeights=[17 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 9), ("RIGHTPADDING", (0, 0), (0, 0), 5),
        ("LEFTPADDING", (1, 0), (1, 0), 5), ("RIGHTPADDING", (1, 0), (1, 0), 9),
        ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
    ]))
    story += [header, Spacer(1, 5 * mm)]

    # TITOLO / STATO / PRIORITA
    title_box = Table([[
        Paragraph(f"<b>Richiesta di intervento</b><br/>{_txt(titolo or 'Senza titolo')}", STYLES["title"]),
        Paragraph(f"<b>STATO</b><br/>{_txt(stato or '—')}", STYLES["value"]),
        _priority_badge(priorita),
    ]], colWidths=[94 * mm, 40 * mm, 40 * mm])
    title_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
    ]))
    story += [title_box, Spacer(1, 5 * mm)]

    # DATI TICKET
    story += [_section_header("DATI DEL TICKET"), Spacer(1, 2 * mm)]
    story.append(_info_table([
        ("Data e ora creazione", _format_date(data_creazione)),
        ("Categoria", categoria),
        ("Priorità", priorita),
        ("Assegnato a", assegnato_a),
        ("Creato da", creato_da),
        ("Stato attuale", stato),
    ]))
    story += [Spacer(1, 3 * mm), _text_box("DESCRIZIONE DEL PROBLEMA", descrizione or "Nessuna descrizione."), Spacer(1, 5 * mm)]

    # FOTO DEL TICKET — solo immagini, nessun nome file
    attachments = _get_attachments(ticket_id)
    ticket_images = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        mime = str(attachment.get("tipo_file") or attachment.get("mime_type") or attachment.get("content_type") or "").lower()
        name = str(attachment.get("nome_file") or "").lower()
        if not (mime.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))):
            continue
        path = attachment.get("percorso_file") or attachment.get("path") or attachment.get("file_path")
        if not path:
            continue
        try:
            raw = db.scarica_allegato(path)
        except Exception:
            raw = None
        image = _image_from_bytes(raw)
        if image:
            ticket_images.append(image)

    if ticket_images:
        story += [_section_header("FOTO DELLA SEGNALAZIONE"), Spacer(1, 3 * mm)]
        for image in ticket_images:
            box = Table([[image]], colWidths=[174 * mm])
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story += [box, Spacer(1, 3 * mm)]

    # STORICO INTERVENTI — tutti gli interventi, non solo l'ultimo
    interventions = _get_interventions(ticket_id)
    if interventions:
        story += [_section_header("STORICO INTERVENTI TECNICI"), Spacer(1, 3 * mm)]

        for number, intervention in enumerate(interventions, start=1):
            if not isinstance(intervention, dict):
                continue
            tecnico = _first(intervention, "tecnico", "technician")
            stato_int = _first(intervention, "stato", "status")
            descr_int = _first(intervention, "descrizione", "descrizione_intervento", "description")
            data_int = _first(intervention, "data_intervento", "created_at", "data")
            foto_path = _first(intervention, "foto_path", "photo_path")
            firma_path = _first(intervention, "firma_path", "signature_path")

            block = [
                Paragraph(f"INTERVENTO #{number}", STYLES["intervention_title"]),
                Spacer(1, 2 * mm),
                _info_table([
                    ("Tecnico", tecnico),
                    ("Stato intervento", stato_int),
                    ("Data e ora", _format_date(data_int)),
                ]),
                Spacer(1, 2 * mm),
                _text_box("DESCRIZIONE INTERVENTO EFFETTUATO", descr_int or "Nessuna descrizione."),
            ]

            if foto_path:
                try:
                    foto = _image_from_bytes(db.scarica_foto_intervento(foto_path), max_width=135 * mm, max_height=72 * mm)
                except Exception:
                    foto = None
                if foto:
                    foto_box = Table([[foto]], colWidths=[174 * mm])
                    foto_box.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]))
                    block += [Spacer(1, 2 * mm), Paragraph("<b>FOTO DELL'INTERVENTO</b>", STYLES["box_title"]), Spacer(1, 1 * mm), foto_box]

            if firma_path:
                try:
                    firma_raw = _scarica_firma(firma_path)
                except Exception:
                    firma_raw = None
            else:
                firma_raw = None
            block += [Spacer(1, 2 * mm), _signature_box("FIRMA DEL TECNICO", firma_raw), Spacer(1, 4 * mm)]

            intervention_table = Table([[block]], colWidths=[174 * mm])
            intervention_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story += [intervention_table, Spacer(1, 5 * mm)]

    # CHIUSURA
    story += [_section_header("CHIUSURA TICKET"), Spacer(1, 2 * mm)]
    story.append(_info_table([
        ("Data chiusura", _format_date(data_chiusura) if data_chiusura else "Non ancora chiuso"),
        ("Chiuso da", chiuso_da or "—"),
    ]))
    story.append(Spacer(1, 3 * mm))

    if chiuso_da:
        try:
            admin_signature = _scarica_firma(chiuso_da, amministratore=True)
        except Exception:
            admin_signature = None
        story.append(_signature_box("FIRMA DEL RESPONSABILE", admin_signature))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return output.getvalue()


__all__ = ["genera_pdf"]
