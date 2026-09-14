# ============================================================
# PDF GENERATOR — GESTIONE TICKET
# Versione grafica aggiornata
#
# Compatibile con views.py:
#     pdf_generator.genera_pdf(ticket)
#
# Non modifica il database e non richiede nuove colonne Supabase.
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
    """
    Converte qualsiasi valore in testo sicuro per ReportLab e lo
    visualizza sempre in MAIUSCOLO nel PDF, indipendentemente da
    come è stato scritto dall'operatore.
    """
    if value is None:
        return ""
    text = str(value).upper()
    return escape(text).replace("\n", "<br/>")


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

    # Formato ISO comune: 2026-09-14T11:20:30...
    try:
        from datetime import datetime

        clean = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _style_paragraph(text, style):
    return Paragraph(_txt(text), style)


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
    """
    rows: lista di tuple (etichetta, valore).
    Crea una griglia 2x2 per riga:
    etichetta | valore | etichetta | valore
    """
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


def _image_from_bytes(raw, max_width=78 * mm, max_height=58 * mm):
    """
    Converte l'allegato in un'immagine ReportLab.
    PIL permette di gestire anche formati che ReportLab potrebbe non
    leggere direttamente.
    """
    if not raw:
        return None

    try:
        if PILImage is not None:
            source = BytesIO(raw)
            pil = PILImage.open(source)

            # Conversione a RGB/RGBA per evitare problemi con palette/transparency.
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


def _get_attachments(ticket_id):
    try:
        result = db.get_allegati(ticket_id)
        return result or []
    except Exception:
        return []


def _get_intervention(ticket_id):
    try:
        return db.get_intervento(ticket_id)
    except Exception:
        return None


# ------------------------------------------------------------
# STILI
# ------------------------------------------------------------

_styles = getSampleStyleSheet()

STYLES = {
    "header": ParagraphStyle(
        "Header",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=19,
        textColor=WHITE,
        alignment=TA_LEFT,
    ),
    "header_right": ParagraphStyle(
        "HeaderRight",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=WHITE,
        alignment=TA_CENTER,
    ),
    "title": ParagraphStyle(
        "Title",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=NAVY,
        alignment=TA_LEFT,
    ),
    "section": ParagraphStyle(
        "Section",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12,
        textColor=WHITE,
        alignment=TA_LEFT,
    ),
    "label": ParagraphStyle(
        "Label",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=MUTED,
    ),
    "value": ParagraphStyle(
        "Value",
        parent=_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=TEXT,
    ),
    "box_title": ParagraphStyle(
        "BoxTitle",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=NAVY,
    ),
    "box_text": ParagraphStyle(
        "BoxText",
        parent=_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXT,
    ),
    "priority": ParagraphStyle(
        "Priority",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10,
        textColor=WHITE,
        alignment=TA_CENTER,
    ),
    "small": ParagraphStyle(
        "Small",
        parent=_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=MUTED,
    ),
    "signature": ParagraphStyle(
        "Signature",
        parent=_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=MUTED,
        alignment=TA_CENTER,
    ),
}


# ------------------------------------------------------------
# FOOTER / HEADER PAGINA
# ------------------------------------------------------------

def _draw_footer(canvas, doc):
    canvas.saveState()

    width, height = A4

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 12 * mm, width - 18 * mm, 12 * mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        18 * mm,
        7.5 * mm,
        "Gestione Ticket — Report Ufficiale",
    )

    page_text = f"Pagina {doc.page}"
    canvas.drawRightString(
        width - 18 * mm,
        7.5 * mm,
        page_text,
    )

    canvas.restoreState()


# ------------------------------------------------------------
# GENERAZIONE PDF
# ------------------------------------------------------------

def genera_pdf(ticket):
    """
    Genera il PDF ufficiale del ticket.

    API mantenuta compatibile con views.py:
        pdf_generator.genera_pdf(ticket)

    Restituisce:
        bytes
    """

    if not ticket:
        raise ValueError("Ticket non valido.")

    ticket_id = _first(ticket, "id")
    titolo = _first(ticket, "titolo", "title")
    stato = _first(ticket, "stato", "status")
    priorita = _first(ticket, "priorita", "priorità", "priority")
    categoria = _first(ticket, "categoria", "category")
    creato_da = _first(ticket, "creato_da", "created_by")
    assegnato_a = _first(ticket, "assegnato_a", "assegnato", "assigned_to")

    data_creazione = _first(
        ticket,
        "creato_il",
        "created_at",
        "data_creazione",
        "created_on",
    )

    data_chiusura = _first(
        ticket,
        "data_chiusura",
        "chiuso_il",
        "closed_at",
        "closed_on",
    )

    chiuso_da = _first(
        ticket,
        "chiuso_da",
        "closed_by",
    )

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
        [
            [
                Paragraph("GESTIONE TICKET", STYLES["header"]),
                Paragraph(
                    f"TICKET #{_txt(ticket_id)}",
                    STYLES["header_right"],
                ),
            ]
        ],
        colWidths=[116 * mm, 58 * mm],
        rowHeights=[17 * mm],
    )

    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 9),
                ("RIGHTPADDING", (0, 0), (0, 0), 5),
                ("LEFTPADDING", (1, 0), (1, 0), 5),
                ("RIGHTPADDING", (1, 0), (1, 0), 9),
                ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
            ]
        )
    )

    story.append(header)
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # TITOLO + STATO + PRIORITA
    # --------------------------------------------------------

    title_box = Table(
        [
            [
                Paragraph(
                    f"<b>Richiesta di intervento</b><br/>{_txt(titolo or 'Senza titolo')}",
                    STYLES["title"],
                ),
                Paragraph(
                    f"<b>STATO</b><br/>{_txt(stato or '—')}",
                    STYLES["value"],
                ),
                _priority_badge(priorita),
            ]
        ],
        colWidths=[94 * mm, 40 * mm, 40 * mm],
    )

    title_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ]
        )
    )

    story.append(title_box)
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # RICHIESTA DI INTERVENTO
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
    # ALLEGATI / FOTO
    # --------------------------------------------------------

    attachments = _get_attachments(ticket_id)

    image_items = []

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue

        tipo = str(
            attachment.get("tipo_file")
            or attachment.get("mime_type")
            or attachment.get("content_type")
            or ""
        ).lower()

        nome = str(attachment.get("nome_file") or "").lower()

        is_image = (
            tipo.startswith("image/")
            or nome.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))
        )

        if not is_image:
            continue

        path = (
            attachment.get("percorso_file")
            or attachment.get("path")
            or attachment.get("file_path")
        )

        if not path:
            continue

        try:
            raw = db.scarica_allegato(path)
        except Exception:
            raw = None

        image = _image_from_bytes(raw)

        if image is not None:
            image_items.append(image)

    if image_items:
        story.append(_section_header("ALLEGATI / FOTO"))
        story.append(Spacer(1, 3 * mm))

        # Una foto per riga: leggibilità massima e nessun nome file.
        for image in image_items:
            image_box = Table([[image]], colWidths=[174 * mm])
            image_box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            story.append(image_box)
            story.append(Spacer(1, 3 * mm))

    # --------------------------------------------------------
    # INTERVENTO TECNICO
    # --------------------------------------------------------

    intervento = _get_intervention(ticket_id)

    if intervento:
        tecnico = _first(intervento, "tecnico", "technician")
        stato_intervento = _first(intervento, "stato", "status")
        descr_intervento = _first(
            intervento,
            "descrizione",
            "descrizione_intervento",
            "description",
        )
        data_intervento = _first(
            intervento,
            "data_intervento",
            "created_at",
            "data",
        )
        firma_path = _first(intervento, "firma_path", "signature_path")

        story.append(_section_header("INTERVENTO TECNICO"))
        story.append(Spacer(1, 2 * mm))

        intervention_metadata = [
            ("Nome del tecnico", tecnico),
            ("Stato intervento", stato_intervento),
            ("Data e ora intervento", _format_date(data_intervento)),
        ]

        story.append(_info_table(intervention_metadata))
        story.append(Spacer(1, 3 * mm))

        # Descrizione intervento: riquadro a tutta larghezza,
        # con titolo sopra e testo sotto, evitando l'etichetta
        # stretta che andava a capo in modo poco elegante.
        intervention_description = Table(
            [
                [Paragraph("DESCRIZIONE INTERVENTO EFFETTUATO", STYLES["box_title"])],
                [Paragraph(_txt(descr_intervento or "Nessuna descrizione."), STYLES["box_text"])],
            ],
            colWidths=[174 * mm],
        )
        intervention_description.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.4, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(intervention_description)
        story.append(Spacer(1, 2 * mm))

        # Firma tecnico
        signature_flowable = None

        if firma_path:
            try:
                raw_signature = db.scarica_firma_intervento(firma_path)
            except Exception:
                raw_signature = None

            signature_flowable = _image_from_bytes(
                raw_signature,
                max_width=55 * mm,
                max_height=30 * mm,
            )

        # Firma tecnica compatta: etichetta a sinistra e firma
        # sulla stessa riga. In questo modo si riduce molto l'altezza
        # occupata e la firma rimane normalmente sulla pagina
        # dell'intervento.
        if signature_flowable:
            signature_content = [
                [
                    Paragraph("FIRMA DEL TECNICO", STYLES["signature"]),
                    signature_flowable,
                ]
            ]
            signature_widths = [42 * mm, 132 * mm]
        else:
            signature_content = [
                [
                    Paragraph("FIRMA DEL TECNICO", STYLES["signature"]),
                    Spacer(1, 10 * mm),
                ]
            ]
            signature_widths = [42 * mm, 132 * mm]

        signature_box = Table(
            signature_content,
            colWidths=signature_widths,
        )
        signature_box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )

        story.append(signature_box)
        story.append(Spacer(1, 3 * mm))

    # --------------------------------------------------------
    # CHIUSURA INTERVENTO
    # --------------------------------------------------------

    story.append(_section_header("CHIUSURA INTERVENTO"))
    story.append(Spacer(1, 2 * mm))

    closure_rows = [
        ("Data chiusura", _format_date(data_chiusura)),
        ("Chiuso da", chiuso_da),
    ]

    if not data_chiusura and not chiuso_da:
        closure_rows = [
            ("Data chiusura", "Non ancora chiuso"),
            ("Chiuso da", "—"),
        ]

    story.append(_info_table(closure_rows))
    story.append(Spacer(1, 4 * mm))

    # Firma automatica dell'amministratore che ha chiuso il ticket.
    responsible_signature_image = None
    if chiuso_da:
        try:
            raw_responsible_signature = db.scarica_firma_amministratore(chiuso_da)
        except Exception:
            raw_responsible_signature = None

        responsible_signature_image = _image_from_bytes(
            raw_responsible_signature,
            max_width=65 * mm,
            max_height=28 * mm,
        )

    if responsible_signature_image:
        responsible_signature = Table(
            [
                [Paragraph("FIRMA DEL RESPONSABILE", STYLES["signature"])],
                [responsible_signature_image],
            ],
            colWidths=[78 * mm],
            hAlign="RIGHT",
        )
    else:
        responsible_signature = Table(
            [
                [Paragraph("FIRMA DEL RESPONSABILE", STYLES["signature"])],
                [Spacer(1, 15 * mm)],
                [Paragraph("____________________________________________", STYLES["small"])],
            ],
            colWidths=[78 * mm],
            hAlign="RIGHT",
        )

    responsible_signature.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), VERY_LIGHT),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    story.append(responsible_signature)

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
