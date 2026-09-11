import html
import io

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import database as db


def _p(text, style):
    return Paragraph(
        html.escape("" if text is None else str(text)).replace("\n", "<br/>"),
        style,
    )


def _p_label_value(label, value, style):
    safe_label = html.escape(str(label))
    safe_value = html.escape("" if value is None else str(value))
    return Paragraph(f"<b>{safe_label}:</b> {safe_value}".replace("\n", "<br/>"), style)


def _image_flowable(data, max_width=160 * mm, max_height=120 * mm):
    """Converte i bytes di un'immagine in un elemento ReportLab ridimensionato."""
    if not data:
        return None

    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size

    if not width or not height:
        return None

    scale = min(max_width / width, max_height / height, 1)
    return RLImage(io.BytesIO(data), width=width * scale, height=height * scale)


def _is_image_attachment(allegato):
    tipo = str(allegato.get("tipo_file") or "").lower().strip()
    nome = str(allegato.get("nome_file") or "").lower().strip()

    if tipo.startswith("image/"):
        return True

    return nome.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))


def genera_pdf(ticket):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Ticket #{ticket.get('id', '')}",
    )

    styles = getSampleStyleSheet()
    
    PRIMARY_COLOR = "#1e3a8a"
    TEXT_COLOR = "#1e293b"
    BG_LIGHT = "#f8fafc"

    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=15,
        textColor=PRIMARY_COLOR,
        fontName="Helvetica-Bold",
    )
    
    heading = ParagraphStyle(
        "HeadingCustom",
        parent=styles["Heading2"],
        spaceBefore=14,
        spaceAfter=6,
        fontSize=12,
        leading=16,
        textColor=PRIMARY_COLOR,
        fontName="Helvetica-Bold",
    )
    
    body = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["BodyText"],
        textColor=TEXT_COLOR,
        fontSize=10,
        leading=14,
    )
    
    body_bold = ParagraphStyle(
        "BodyTextBoldCustom",
        parent=body,
        fontName="Helvetica-Bold",
    )

    story = [
        _p(f"GESTIONE TICKET — #{ticket.get('id', '')}", title_style),
        Spacer(1, 2 * mm),
    ]

    rows = [
        ["Titolo", ticket.get("titolo", "")],
        ["Stato", ticket.get("stato", "")],
        ["Priorità", ticket.get("priorita", "")],
        ["Categoria", ticket.get("categoria", "")],
        ["Creato da", ticket.get("creato_da", "")],
        ["Assegnato a", ticket.get("assegnato_a", "")],
        ["Creato il", db.format_data(ticket.get("creato_il"))],
    ]

    table_data = [[_p(k, body_bold), _p(v, body)] for k, v in rows]
    table = Table(table_data, colWidths=[40 * mm, 137 * mm], repeatRows=0)
    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, "#cbd5e1"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), BG_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story += [table, Spacer(1, 6 * mm)]

    story.append(_p("Descrizione", heading))
    story.append(_p(ticket.get("descrizione", ""), body))

    allegati = db.get_allegati(ticket.get("id"))
    immagini_inserite = 0

    if allegati:
        for allegato in allegati:
            if not _is_image_attachment(allegato):
                continue

            percorso = allegato.get("percorso_file")
            if not percorso:
                continue

            try:
                data = db.scarica_allegato(percorso)
                flow = _image_flowable(data)
                if flow:
                    if immagini_inserite == 0:
                        story.append(_p("Allegati / Foto", heading))
                    story += [
                        Spacer(1, 3 * mm),
                        flow,
                        Spacer(1, 5 * mm),
                    ]
                    immagini_inserite += 1
            except Exception:
                continue

    intervento = db.get_intervento(ticket.get("id"))
    if intervento:
        story.append(_p("Intervento tecnico", heading))
        story.append(_p_label_value("Tecnico", intervento.get('tecnico', ''), body))
        story.append(_p_label_value("Stato", intervento.get('stato', ''), body))
        
        # Descrizione intervento posizionata subito sotto lo stato
        desc_intervento = intervento.get("descrizione", "")
        if desc_intervento:
            story.append(Spacer(1, 2 * mm))
            story.append(_p(desc_intervento, body))
        
        # Data intervento posizionata prima della firma
        data_int = intervento.get('data_intervento')
        if data_int:
            story.append(Spacer(1, 2 * mm))
            story.append(_p_label_value("Data Intervento", db.format_data(data_int), body))

        firma_path = intervento.get("firma_path")
        if firma_path:
            try:
                story.append(Spacer(1, 4 * mm))
                story.append(_p("Firma del tecnico", heading))
                firma_data = db.scarica_firma_intervento(firma_path)
                firma_flow = _image_flowable(firma_data, 70 * mm, 35 * mm)
                if firma_flow:
                    story += [firma_flow, Spacer(1, 4 * mm)]
            except Exception:
                pass

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(15 * mm, 10 * mm, "Gestione Ticket — Report Ufficiale")
        canvas.drawRightString(195 * mm, 10 * mm, f"Pagina {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
