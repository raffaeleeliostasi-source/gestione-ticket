# ============================================================
# PDF GENERATOR — GESTIONE TICKET
# Versione con Cronologia Interventi e Firma Amministratore
# (Firme dei tecnici solo nel blocco finale)
# ============================================================

from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
)
from reportlab.pdfbase.pdfmetrics import stringWidth

try:
    from PIL import Image as PILImage
except Exception:
    PILImage = None

import database as db


# ------------------------------------------------------------
# COLORI
# ------------------------------------------------------------

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
LIGHT_BLUE = colors.HexColor("#EAF3FB")
VERY_LIGHT = colors.HexColor("#F6F8FA")
BORDER = colors.HexColor("#D5DDE5")
TEXT = colors.HexColor("#263238")
MUTED = colors.HexColor("#66727D")
WHITE = colors.white

PRIORITY_COLORS = {
    "bassa": colors.HexColor("#15803D"),
    "media": colors.HexColor("#CA8A04"),
    "alta": colors.HexColor("#EA580C"),
    "urgente": colors.HexColor("#B91C1C"),
}


# ------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ------------------------------------------------------------

def _txt(value):
    """Converte qualsiasi valore in testo sicuro per ReportLab."""
    if value is None:
        return ""
    return escape(str(value)).replace("\n", "<br/>")


def _first(ticket, *keys):
    """Restituisce il primo valore valorizzato tra le chiavi indicate."""
    for key in keys:
        value = ticket.get(key)
        if value not in (None, ""):
            return value
    return ""


def _format_date(value):
    """Formatta le date senza dipendere dal tipo restituito da Supabase."""
    if value in (None, ""):
        return ""

    try:
        return db.format_data(value)
    except Exception:
        pass

    text = str(value).strip()
    if not text:
        return ""

    try:
        from datetime import datetime

        clean = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _section_header(title):
    t = Table(
        [[Paragraph(_txt(title), STYLES["section"])]],
        colWidths=[174 * mm],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
            ]
        )
    )
    return t


def _info_table(rows, widths=(43 * mm, 44 * mm, 43 * mm, 44 * mm)):
    data = []
    for i in range(0, len(rows), 2):
        row = []
        first = rows[i]
        row.extend(
            [
                Paragraph(_txt(first[0]), STYLES["label"]),
                Paragraph(_txt(first[1]), STYLES["value"]),
            ]
        )

        if i + 1 < len(rows):
            second = rows[i + 1]
            row.extend(
                [
                    Paragraph(_txt(second[0]), STYLES["label"]),
                    Paragraph(_txt(second[1]), STYLES["value"]),
                ]
            )
        else:
            row.extend(["", ""])

        data.append(row)

    table = Table(data, colWidths=list(widths), repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _box(title, text, background=colors.white):
    content = [
        [
            Paragraph(_txt(title), STYLES["box_title"]),
            Paragraph(_txt(text), STYLES["box_text"]),
        ]
    ]
    table = Table(content, colWidths=[38 * mm, 136 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _priority_badge(priority):
    value = str(priority or "").strip()
    bg = PRIORITY_COLORS.get(value.lower(), BLUE)

    badge = Table(
        [[Paragraph(_txt(value or "—"), STYLES["priority"])]],
        colWidths=[31 * mm],
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, bg),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return badge


def _image_from_bytes(raw, max_width=82 * mm, max_height=72 * mm):
    if not raw:
        return None

    try:
        if PILImage is not None:
            source = BytesIO(raw)
            pil = PILImage.open(source)

            if pil.mode not in ("RGB", "RGBA"):
                pil = pil.convert("RGB")

            out = BytesIO()
            fmt = "PNG" if pil.mode == "RGBA" else "JPEG"
            pil.save(out, format=fmt)
            out.seek(0)

            img = RLImage(out)
        else:
            img = RLImage(BytesIO(raw))

        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None

        scale = min(max_width / iw, max_height / ih, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale

        img.hAlign = "CENTER"
        return img

    except Exception:
        return None


# ------------------------------------------------------------
# STILI
# ------------------------------------------------------------

_styles = getSampleStyleSheet()

STYLES = {
    "header": ParagraphStyle(
        "Header", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=17, leading=19, textColor=WHITE, alignment=TA_LEFT
    ),
    "header_right": ParagraphStyle(
        "HeaderRight", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=WHITE, alignment=TA_CENTER
    ),
    "title": ParagraphStyle(
        "Title", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=TA_LEFT
    ),
    "section": ParagraphStyle(
        "Section", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=WHITE, alignment=TA_LEFT
    ),
    "label": ParagraphStyle(
        "Label", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=MUTED
    ),
    "value": ParagraphStyle(
        "Value", parent=_styles["Normal"], fontName="Helvetica", fontSize=9, leading=11, textColor=TEXT
    ),
    "box_title": ParagraphStyle(
        "BoxTitle", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=NAVY
    ),
    "box_text": ParagraphStyle(
        "BoxText", parent=_styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT
    ),
    "priority": ParagraphStyle(
        "Priority", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=10, textColor=WHITE, alignment=TA_CENTER
    ),
    "small": ParagraphStyle(
        "Small", parent=_styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9, textColor=MUTED
    ),
    "signature": ParagraphStyle(
        "Signature", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER
    ),
}


# ------------------------------------------------------------
# FOOTER PAGINA
# ------------------------------------------------------------

def _draw_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 12 * mm, width - 18 * mm, 12 * mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 7.5 * mm, "Gestione Ticket — Report Ufficiale")
    canvas.drawRightString(width - 18 * mm, 7.5 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------
# GENERAZIONE PDF
# ------------------------------------------------------------

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
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"Ticket #{ticket_id}",
        author="Gestione Ticket",
    )

    story = []

    # --------------------------------------------------------
    # TESTATA
    # --------------------------------------------------------
    header = Table(
        [[
            Paragraph("GESTIONE TICKET", STYLES["header"]),
            Paragraph(f"TICKET #{_txt(ticket_id)}", STYLES["header_right"]),
        ]],
        colWidths=[116 * mm, 58 * mm],
        rowHeights=[17 * mm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 9),
        ("RIGHTPADDING", (0, 0), (0, 0), 5),
        ("LEFTPADDING", (1, 0), (1, 0), 5),
        ("RIGHTPADDING", (1, 0), (1, 0), 9),
        ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
    ]))
    story.append(header)
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # TITOLO + STATO + PRIORITA
    # --------------------------------------------------------
    title_box = Table(
        [[
            Paragraph(f"<b>Richiesta di intervento</b><br/>{_txt(titolo or 'Senza titolo')}", STYLES["title"]),
            Paragraph(f"<b>STATO</b><br/>{_txt(stato or '—')}", STYLES["value"]),
            _priority_badge(priorita),
        ]],
        colWidths=[94 * mm, 40 * mm, 40 * mm],
    )
    title_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
    ]))
    story.append(title_box)
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # DETTAGLI INIZIALI
    # --------------------------------------------------------
    story.append(_section_header("RICHIESTA DI INTERVENTO"))
    story.append(Spacer(1, 2 * mm))

    metadata = [
        ("Data e ora creazione", _format_date(data_creazione)),
        ("Categoria", categoria),
        ("Priorità", priorita),
        ("Assegnato a", assegnato_a),
        ("Creato da", creato_da),
        ("Stato attuale", stato),
    ]
    story.append(_info_table(metadata))
    story.append(Spacer(1, 3 * mm))
    story.append(_box("DESCRIZIONE", descrizione or "Nessuna descrizione."))
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # ALLEGATI / FOTO PRINCIPALI DEL TICKET
    # --------------------------------------------------------
    try:
        attachments = db.get_allegati(ticket_id) or []
    except Exception:
        attachments = []

    image_items = []
    for attachment in attachments:
        tipo = str(attachment.get("tipo_file") or "").lower()
        nome = str(attachment.get("nome_file") or "").lower()
        if tipo.startswith("image/") or nome.endswith((".jpg", ".jpeg", ".png", ".webp")):
            path = attachment.get("percorso_file")
            if path:
                try:
                    raw = db.scarica_allegato(path)
                    img = _image_from_bytes(raw)
                    if img:
                        image_items.append(img)
                except Exception:
                    pass

    if image_items:
        story.append(_section_header("ALLEGATI / FOTO"))
        story.append(Spacer(1, 3 * mm))
        for img in image_items:
            img_box = Table([[img]], colWidths=[174 * mm])
            img_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(img_box)
            story.append(Spacer(1, 3 * mm))

    # --------------------------------------------------------
    # CRONOLOGIA INTERVENTI TECNICI (Senza firme nei singoli blocchi)
    # --------------------------------------------------------
    try:
        interventi = db.get_interventi(ticket_id) or []
    except Exception:
        interventi = []

    if interventi:
        story.append(_section_header(f"CRONOLOGIA INTERVENTI TECNICI ({len(interventi)})"))
        story.append(Spacer(1, 3 * mm))

        for idx, intervento in enumerate(interventi, start=1):
            t_tecnico = _first(intervento, "tecnico")
            t_stato = _first(intervento, "stato")
            t_data = _format_date(_first(intervento, "data_intervento"))
            t_descr = _first(intervento, "descrizione")

            int_meta = [
                ("N. Intervento", f"#{idx}"),
                ("Tecnico", t_tecnico),
                ("Stato", t_stato),
                ("Data e ora", t_data),
            ]
            story.append(_info_table(int_meta))
            story.append(Spacer(1, 2 * mm))
            story.append(_box(f"INTERVENTO #{idx}", t_descr or "Nessuna descrizione."))
            story.append(Spacer(1, 2 * mm))

            # Foto dell'intervento se presente
            foto_path = intervento.get("foto_path")
            if foto_path:
                try:
                    foto_bytes = db.scarica_foto_intervento(foto_path)
                    f_img = _image_from_bytes(foto_bytes)
                    if f_img:
                        f_box = Table([[f_img]], colWidths=[174 * mm])
                        f_box.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]))
                        story.append(f_box)
                        story.append(Spacer(1, 2 * mm))
                except Exception:
                    pass

            story.append(Spacer(1, 3 * mm))

    # --------------------------------------------------------
    # CHIUSURA TICKET
    # --------------------------------------------------------
    story.append(_section_header("CHIUSURA TICKET"))
    story.append(Spacer(1, 2 * mm))

    closure_rows = [
        ("Data chiusura", _format_date(data_chiusura) if data_chiusura else "Non ancora chiuso"),
        ("Chiuso da", chiuso_da or "—"),
    ]
    story.append(_info_table(closure_rows))
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # FIRME FINALI (TECNICO DELL'ULTIMO INTERVENTO + AMMINISTRATORE)
    # --------------------------------------------------------
    tech_signature = None
    if interventi:
        ultimo_intervento = interventi[-1]
        last_firma_path = ultimo_intervento.get("firma_path")
        if not last_firma_path and ultimo_intervento.get("id"):
            last_firma_path = f"firme/{ticket_id}/intervento_{ultimo_intervento.get('id')}/firma.png"
        if last_firma_path:
            try:
                raw_sig = db.scarica_firma_intervento(last_firma_path)
                tech_signature = _image_from_bytes(raw_sig, max_width=62 * mm, max_height=22 * mm)
            except Exception:
                tech_signature = None

    admin_signature = None
    admin_name_to_check = chiuso_da if chiuso_da else None
    if admin_name_to_check:
        try:
            raw_admin_sig = db.scarica_firma_amministratore(admin_name_to_check)
            if raw_admin_sig:
                admin_signature = _image_from_bytes(raw_admin_sig, max_width=62 * mm, max_height=22 * mm)
        except Exception:
            admin_signature = None

    def _signature_box(title, signature=None):
        cell = [
            [Paragraph(title, STYLES["signature"])],
            [signature if signature is not None else Spacer(1, 20 * mm)],
            [Paragraph("________________________________", STYLES["small"])],
        ]
        box = Table(
            cell,
            colWidths=[82 * mm],
            rowHeights=[8 * mm, 24 * mm, 7 * mm],
        )
        box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return box

    signatures = Table(
        [[
            _signature_box("FIRMA DEL TECNICO", tech_signature),
            _signature_box(f"FIRMA AMMINISTRATORE{f' ({chiuso_da})' if chiuso_da else ''}", admin_signature),
        ]],
        colWidths=[87 * mm, 87 * mm],
    )
    signatures.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(signatures)

    # --------------------------------------------------------
    # COSTRUZIONE
    # --------------------------------------------------------
    doc.build(
        story,
        onFirstPage=_draw_footer,
        onLaterPages=_draw_footer,
    )

    return output.getvalue()


__all__ = ["genera_pdf"]
