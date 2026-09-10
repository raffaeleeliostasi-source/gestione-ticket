from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from database import get_intervento, get_allegati, scarica_allegato, scarica_firma_intervento, format_data

def genera_pdf(ticket):
    buffer = BytesIO()
    styles = getSampleStyleSheet()

    stile_titolo = styles["Title"].clone("TicketTitle")
    stile_titolo.fontName = "Helvetica-Bold"
    stile_titolo.fontSize = 20
    stile_titolo.leading = 24

    stile_sottotitolo = styles["Normal"].clone("TicketSubtitle")
    stile_sottotitolo.fontSize = 9
    stile_sottotitolo.textColor = colors.grey

    stile_sezione = styles["Heading2"].clone("TicketSection")
    stile_sezione.fontName = "Helvetica-Bold"
    stile_sezione.fontSize = 13
    stile_sezione.spaceBefore = 10

    stile_testo = styles["BodyText"].clone("TicketBody")
    stile_testo.fontSize = 9.5
    stile_testo.leading = 14

    def testo_pdf(valore):
        if not valore:
            return "-"
        return str(valore).strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

    def intestazione_pagina(canvas, doc):
        canvas.saveState()
        larghezza, altezza = A4
        canvas.setStrokeColor(colors.HexColor("#D9D9D9"))
        canvas.line(40, altezza - 42, larghezza - 40, altezza - 42)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(40, altezza - 32, "GESTIONE TICKET")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(larghezza - 40, altezza - 32, f"Ticket #{ticket.get('id', '')}")
        canvas.line(40, 35, larghezza - 40, 35)
        canvas.drawString(40, 23, "Report generato automaticamente")
        canvas.drawRightString(larghezza - 40, 23, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=58, bottomMargin=48)
    elementi = [
        Paragraph(f"Ticket #{testo_pdf(ticket.get('id', ''))}", stile_titolo),
        Paragraph(testo_pdf(ticket.get("titolo", "Senza titolo")), stile_sottotitolo),
        Paragraph("Riepilogo ticket", stile_sezione)
    ]

    dati = [
        ["Categoria", testo_pdf(ticket.get("categoria", ""))],
        ["Priorità", testo_pdf(ticket.get("priorita", ""))],
        ["Stato", testo_pdf(ticket.get("stato", ""))],
        ["Creato da", testo_pdf(ticket.get("creato_da", ""))],
        ["Assegnato a", testo_pdf(ticket.get("assegnato_a", ""))]
    ]
    tabella = Table(dati, colWidths=[125, 365])
    tabella.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F3F5")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D4D8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6)
    ]))
    elementi.extend([tabella, Paragraph("Problema segnalato", stile_sezione), Paragraph(testo_pdf(ticket.get("descrizione", "")), stile_testo)])

    intervento = get_intervento(ticket["id"])
    if intervento:
        elementi.append(Paragraph("Intervento tecnico", stile_sezione))
        dati_int = [
            ["Tecnico", testo_pdf(intervento.get("tecnico", ""))],
            ["Data intervento", testo_pdf(format_data(intervento.get("data_intervento")))],
            ["Esito", testo_pdf(intervento.get("stato", ""))]
        ]
        t_int = Table(dati_int, colWidths=[125, 365])
        t_int.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F3F5")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D4D8")),
            ("PADDING", (0, 0), (-1, -1), 6)
        ]))
        elementi.extend([t_int, Spacer(1, 10), Paragraph("Descrizione dell'intervento", styles["Heading3"]), Paragraph(testo_pdf(intervento.get("descrizione", "")), stile_testo)])

        firma_path = intervento.get("firma_path")
        if firma_path:
            firma_bytes = scarica_firma_intervento(firma_path)
            if firma_bytes:
                try:
                    firma_reader = ImageReader(BytesIO(firma_bytes))
                    w, h = firma_reader.getSize()
                    rapporto = min(250 / w, 90 / h, 1)
                    elementi.extend([Spacer(1, 10), Paragraph("Firma del tecnico", styles["Heading3"]), RLImage(BytesIO(firma_bytes), width=w*rapporto, height=h*rapporto)])
                except Exception:
                    pass

    allegati = get_allegati(ticket["id"])
    for allegato in allegati:
        if allegato.get("tipo_file", "").startswith("image/") and allegato.get("percorso_file"):
            contenuto = scarica_allegato(allegato["percorso_file"])
            if contenuto:
                try:
                    img_reader = ImageReader(BytesIO(contenuto))
                    w, h = img_reader.getSize()
                    rapporto = min(490 / w, 520 / h, 1)
                    elementi.extend([Paragraph(testo_pdf(allegato.get("nome_file")), stile_sottotitolo), RLImage(BytesIO(contenuto), width=w*rapporto, height=h*rapporto), Spacer(1, 10)])
                except Exception:
                    pass

    doc.build(elementi, onFirstPage=intestazione_pagina, onLaterPages=intestazione_pagina)
    buffer.seek(0)
    return buffer.getvalue()
