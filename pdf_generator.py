import html
import io
from pathlib import Path

from PIL import Image
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
    return Paragraph(html.escape("" if text is None else str(text)).replace("\n", "<br/>"), style)


def _image_flowable(data, max_width=160 * mm, max_height=95 * mm):
    image = Image.open(io.BytesIO(data))
    width, height = image.size
    if not width or not height:
        return None

    scale = min(max_width / width, max_height / height, 1)
    return RLImage(io.BytesIO(data), width=width * scale, height=height * scale)


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
    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        spaceBefore=10,
        spaceAfter=6,
    )
    body = styles["BodyText"]

    story = [
        _p(f"GESTIONE TICKET — #{ticket.get('id', '')}", title_style),
        Spacer(1, 4 * mm),
    ]

    rows = [
        ["Titolo", ticket.get("titolo", "")],
        ["Stato", ticket.get("stato", "")],
        ["Priorità", ticket.get("priorita", "")],
        ["Categoria", ticket.get("categoria", "")],
        ["Creato da", ticket.get("creato_da", "")],
        ["Assegnato a", ticket.get("assegnato_a", "")],
    ]

    table_data = [[_p(k, body), _p(v, body)] for k, v in rows]
    table = Table(table_data, colWidths=[38 * mm, 137 * mm], repeatRows=0)
    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, "#999999"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), "#eeeeee"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story += [table, Spacer(1, 5 * mm)]

    story.append(_p("Descrizione", heading))
    story.append(_p(ticket.get("descrizione", ""), body))

    allegati = db.get_allegati(ticket.get("id"))
    if allegati:
        story.append(_p("Allegati", heading))
        for allegato in allegati:
            nome = allegato.get("nome_file", "allegato")
            mime = allegato.get("tipo_file", "") or ""
            ext = Path(nome).suffix.lower()
            is_image = mime.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            story.append(_p(f"• {nome}", body))
            if is_image:
                try:
                    data = db.scarica_allegato(allegato.get("percorso_file"))
                    flow = _image_flowable(data)
                    if flow:
                        story += [Spacer(1, 2 * mm), flow, Spacer(1, 3 * mm)]
                except Exception:
                    pass

    intervento = db.get_intervento(ticket.get("id"))
    if intervento:
        story.append(_p("Intervento tecnico", heading))
        story.append(_p(f"Tecnico: {intervento.get('tecnico', '')}", body))
        story.append(_p(f"Stato: {intervento.get('stato', '')}", body))
        descrizione_intervento = intervento.get("descrizione", "")
        if descrizione_intervento:
            story.append(_p("Descrizione intervento:", body))
            story.append(_p(descrizione_intervento, body))

        firma_path = intervento.get("firma_path")
        if firma_path:
            try:
                story.append(_p("Firma del tecnico", heading))
                firma_data = db.scarica_firma_intervento(firma_path)
                firma_flow = _image_flowable(firma_data, 80 * mm, 40 * mm)
                if firma_flow:
                    story += [firma_flow, Spacer(1, 4 * mm)]
            except Exception:
                pass

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(15 * mm, 8 * mm, "Gestione Ticket")
        canvas.drawRightString(195 * mm, 8 * mm, f"Pagina {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
