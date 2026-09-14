import html
import io

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import database as db


# ============================================================
# UTILITÀ
# ============================================================

def _p(text, style):
    return Paragraph(
        html.escape("" if text is None else str(text)).replace("\n", "<br/>"),
        style,
    )


def _p_label_value(label, value, style):
    safe_label = html.escape(str(label))
    safe_value = html.escape("" if value is None else str(value))
    return Paragraph(
        f"<b>{safe_label}:</b> {safe_value}".replace("\n", "<br/>"),
        style,
    )


def _image_flowable(data, max_width=165 * mm, max_height=105 * mm):
    """Converte i bytes di un'immagine in un elemento ReportLab ridimensionato."""
    if not data:
        return None

    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
    except Exception:
        return None

    if not width or not height:
        return None

    scale = min(max_width / width, max_height / height, 1)
    return RLImage(
        io.BytesIO(data),
        width=width * scale,
        height=height * scale,
    )


def _is_image_attachment(allegato):
    tipo = str(allegato.get("tipo_file") or "").lower().strip()
    nome = str(allegato.get("nome_file") or "").lower().strip()

    if tipo.startswith("image/"):
        return True

    return nome.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))


def _priority_color(priority):
    """Colore semantico della priorità."""
    p = str(priority or "").strip().lower()

    if p == "urgente":
        return colors.HexColor("#b91c1c")       # rosso
    if p == "alta":
        return colors.HexColor("#ea580c")       # arancio
    if p == "media":
        return colors.HexColor("#ca8a04")       # giallo/oro
    if p == "bassa":
        return colors.HexColor("#15803d")       # verde

    return colors.HexColor("#475569")


def _priority_badge(priority, style):
    value = str(priority or "")
    badge_style = ParagraphStyle(
        "PriorityBadge",
        parent=style,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )

    badge = Table([[_p(value, badge_style)]], colWidths=[32 * mm])
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _priority_color(value)),
                ("BOX", (0, 0), (-1, -1), 0.5, _priority_color(value)),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return badge


# ============================================================
# GENERAZIONE PDF
# ============================================================

def genera_pdf(ticket):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Ticket #{ticket.get('id', '')}",
        author="Gestione Ticket",
    )

    styles = getSampleStyleSheet()

    # Palette grafica
    NAVY = colors.HexColor("#17324D")
    BLUE = colors.HexColor("#2563EB")
    LIGHT_BLUE = colors.HexColor("#EFF6FF")
    LIGHT_GREY = colors.HexColor("#F8FAFC")
    BORDER = colors.HexColor("#CBD5E1")
    TEXT = colors.HexColor("#1E293B")
    MUTED = colors.HexColor("#64748B")
    WHITE = colors.white

    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Title"],
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=NAVY,
        spaceAfter=2,
    )

    subtitle_style = ParagraphStyle(
        "TicketSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=MUTED,
        spaceAfter=0,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=WHITE,
        spaceBefore=0,
        spaceAfter=0,
    )

    body = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=TEXT,
        spaceAfter=0,
    )

    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body,
        fontName="Helvetica-Bold",
    )

    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=8.5,
        leading=11,
        textColor=MUTED,
    )

    signature_label = ParagraphStyle(
        "SignatureLabel",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=NAVY,
    )

    story = []

    # --------------------------------------------------------
    # INTESTAZIONE
    # --------------------------------------------------------

    ticket_id = ticket.get("id", "")
    titolo = ticket.get("titolo", "")

    header_left = [
        _p("GESTIONE TICKET", title_style),
        _p(f"Richiesta di intervento — Ticket #{ticket_id}", subtitle_style),
    ]

    header = Table(
        [[header_left, _priority_badge(ticket.get("priorita"), body)]],
        colWidths=[145 * mm, 32 * mm],
        hAlign="LEFT",
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 5 * mm))

    # Titolo evidenziato
    title_box = Table(
        [[
            _p(
                f"<b>{html.escape(str(titolo or ''))}</b>",
                ParagraphStyle(
                    "MainTicketTitle",
                    parent=body,
                    fontSize=12,
                    leading=15,
                    textColor=NAVY,
                ),
            )
        ]],
        colWidths=[177 * mm],
    )
    title_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#BFDBFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(title_box)
    story.append(Spacer(1, 6 * mm))

    # --------------------------------------------------------
    # SEZIONE RICHIESTA DI INTERVENTO
    # --------------------------------------------------------

    section_header = Table(
        [[_p("RICHIESTA DI INTERVENTO", section_style)]],
        colWidths=[177 * mm],
    )
    section_header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(section_header)
    story.append(Spacer(1, 2 * mm))

    data_creazione = ticket.get("creato_il") or ticket.get("created_at")

    request_rows = [
        [_p("Data e ora creazione ticket", body_bold), _p(db.format_data(data_creazione), body)],
        [_p("Categoria", body_bold), _p(ticket.get("categoria", ""), body)],
        [_p("Priorità", body_bold), _priority_badge(ticket.get("priorita"), body)],
        [_p("Assegnato a", body_bold), _p(ticket.get("assegnato_a", ""), body)],
        [_p("Creato da", body_bold), _p(ticket.get("creato_da", ""), body)],
        [_p("Stato", body_bold), _p(ticket.get("stato", ""), body)],
    ]

    request_table = Table(
        request_rows,
        colWidths=[62 * mm, 115 * mm],
    )
    request_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(request_table)
    story.append(Spacer(1, 4 * mm))

    story.append(_p("Descrizione", body_bold))
    story.append(Spacer(1, 1.5 * mm))

    description_box = Table(
        [[_p(ticket.get("descrizione", ""), body)]],
        colWidths=[177 * mm],
    )
    description_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(description_box)
    story.append(Spacer(1, 5 * mm))

    # --------------------------------------------------------
    # FOTO DEL PROBLEMA
    # --------------------------------------------------------

    allegati = db.get_allegati(ticket_id)
    immagini = []

    for allegato in allegati or []:
        if not _is_image_attachment(allegato):
            continue

        percorso = allegato.get("percorso_file")
        if not percorso:
            continue

        try:
            data = db.scarica_allegato(percorso)
            flow = _image_flowable(data)
            if flow:
                immagini.append(flow)
        except Exception:
            continue

    if immagini:
        story.append(
            Table(
                [[_p("ALLEGATI / FOTO", section_style)]],
                colWidths=[177 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
        )
        story.append(Spacer(1, 3 * mm))

        for image_flow in immagini:
            image_flow.hAlign = "CENTER"
            story.append(image_flow)
            story.append(Spacer(1, 4 * mm))

    # --------------------------------------------------------
    # INTERVENTO TECNICO
    # --------------------------------------------------------

    intervento = db.get_intervento(ticket_id)

    if intervento:
        story.append(Spacer(1, 2 * mm))
        story.append(
            Table(
                [[_p("INTERVENTO TECNICO", section_style)]],
                colWidths=[177 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
        )
        story.append(Spacer(1, 2 * mm))

        tech_rows = [
            [_p("Nome del tecnico", body_bold), _p(intervento.get("tecnico", ""), body)],
            [_p("Stato", body_bold), _p(intervento.get("stato", ""), body)],
            [_p("Data e ora intervento", body_bold), _p(db.format_data(intervento.get("data_intervento")), body)],
        ]

        tech_table = Table(tech_rows, colWidths=[62 * mm, 115 * mm])
        tech_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
                    ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(tech_table)
        story.append(Spacer(1, 4 * mm))

        story.append(_p("Descrizione intervento effettuato", body_bold))
        story.append(Spacer(1, 1.5 * mm))

        intervention_box = Table(
            [[_p(intervento.get("descrizione", ""), body)]],
            colWidths=[177 * mm],
        )
        intervention_box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(intervention_box)
        story.append(Spacer(1, 5 * mm))

        # Foto dell'intervento: il database attuale non distingue le foto
        # del problema da quelle dell'intervento. Vengono quindi mostrate
        # tutte le immagini associate al ticket, senza nome file.

        firma_path = intervento.get("firma_path")
        firma_flow = None

        if firma_path:
            try:
                firma_data = db.scarica_firma_intervento(firma_path)
                firma_flow = _image_flowable(
                    firma_data,
                    max_width=70 * mm,
                    max_height=30 * mm,
                )
            except Exception:
                firma_flow = None

        signature_cells = []

        if firma_flow:
            firma_flow.hAlign = "LEFT"
            signature_cells.append(
                [
                    _p("Firma del tecnico", signature_label),
                    firma_flow,
                ]
            )
        else:
            signature_cells.append(
                [
                    _p("Firma del tecnico", signature_label),
                    Spacer(1, 12 * mm),
                ]
            )

        signature_table = Table(
            signature_cells,
            colWidths=[55 * mm, 122 * mm],
        )
        signature_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (1, 0), (1, 0), 0.6, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(signature_table)

    # --------------------------------------------------------
    # CHIUSURA INTERVENTO
    # --------------------------------------------------------

    data_chiusura = ticket.get("data_chiusura")
    chiuso_da = ticket.get("chiuso_da")

    if data_chiusura or chiuso_da or str(ticket.get("stato", "")).strip() == "Chiuso":
        story.append(Spacer(1, 6 * mm))

        story.append(
            Table(
                [[_p("CHIUSURA INTERVENTO", section_style)]],
                colWidths=[177 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
        )
        story.append(Spacer(1, 2 * mm))

        close_rows = [
            [_p("Data chiusura", body_bold), _p(db.format_data(data_chiusura), body)],
            [_p("Chiuso da", body_bold), _p(chiuso_da or "", body)],
        ]

        close_table = Table(close_rows, colWidths=[62 * mm, 115 * mm])
        close_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
                    ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(close_table)
        story.append(Spacer(1, 5 * mm))

        # Il DB attuale non contiene ancora una firma digitale del responsabile.
        responsible_signature = Table(
            [
                [
                    _p("Firma del Responsabile", signature_label),
                    Spacer(1, 12 * mm),
                ]
            ],
            colWidths=[55 * mm, 122 * mm],
        )
        responsible_signature.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (1, 0), (1, 0), 0.6, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(responsible_signature)

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    def footer(canvas, doc_obj):
        canvas.saveState()

        width, height = A4

        # linea superiore footer
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(15 * mm, 13 * mm, width - 15 * mm, 13 * mm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            15 * mm,
            8 * mm,
            "Gestione Ticket — Report Ufficiale",
        )
        canvas.drawRightString(
            width - 15 * mm,
            8 * mm,
            f"Pagina {doc_obj.page}",
        )

        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )

    return buffer.getvalue()
