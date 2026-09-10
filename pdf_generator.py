import io
import requests
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import database as db

def genera_pdf(ticket):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    tid = ticket.get("id")

    # Stili personalizzati
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=0
    )
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=10
    )
    normal_style = styles['Normal']

    # --- INTESTAZIONE ---
    story.append(Paragraph(f"<b>REPORT TICKET #{tid}</b>", title_style))
    story.append(Spacer(1, 12))

    # --- TABELLA DETTAGLI TICKET ---
    data_ticket = [
        [Paragraph("<b>Titolo:</b>", normal_style), Paragraph(str(ticket.get("titolo", "")), normal_style)],
        [Paragraph("<b>Stato:</b>", normal_style), Paragraph(str(ticket.get("stato", "")), normal_style)],
        [Paragraph("<b>Priorità:</b>", normal_style), Paragraph(str(ticket.get("priorita", "")), normal_style)],
        [Paragraph("<b>Categoria:</b>", normal_style), Paragraph(str(ticket.get("categoria", "")), normal_style)],
        [Paragraph("<b>Creato da:</b>", normal_style), Paragraph(str(ticket.get("creato_da", "")), normal_style)],
        [Paragraph("<b>Tecnico Assegnato:</b>", normal_style), Paragraph(str(ticket.get("assegnato_a", "")), normal_style)],
    ]

    t_ticket = Table(data_ticket, colWidths=[130, 400])
    t_ticket.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_ticket)
    story.append(Spacer(1, 12))

    # --- DESCRIZIONE PROBLEMA ---
    story.append(Paragraph("<b>Descrizione del Problema:</b>", h2_style))
    story.append(Paragraph(str(ticket.get("descrizione", "")), normal_style))
    story.append(Spacer(1, 12))

    # --- FOTO / ALLEGATI (Tabella corretta: ticket_allegati) ---
    try:
        res_all = db.supabase.table("ticket_allegati").select("*").eq("ticket_id", tid).execute()
        allegati = res_all.data if res_all and res_all.data else []
    except Exception:
        allegati = []

    if allegati:
        story.append(Paragraph("<b>Foto e Allegati:</b>", h2_style))
        for allegato in allegati:
            file_path = allegato.get("percorso_file") or allegato.get("file_path") or allegato.get("url")
            if file_path:
                try:
                    img_bytes = None
                    if isinstance(file_path, str) and file_path.startswith("http"):
                        res = requests.get(file_path, timeout=5)
                        if res.status_code == 200:
                            img_bytes = io.BytesIO(res.content)
                    elif isinstance(file_path, str):
                        # Scarica dal bucket "allegati"
                        data = db.supabase.storage.from_("allegati").download(file_path)
                        img_bytes = io.BytesIO(data)

                    if img_bytes:
                        story.append(RLImage(img_bytes, width=200, height=150))
                        story.append(Spacer(1, 8))
                except Exception as e:
                    print(f"Errore caricamento allegato PDF: {e}")

    # --- DETTAGLI INTERVENTO (Tabella corretta: ticket_interventi) ---
    intervento = None
    try:
        res_int = db.supabase.table("ticket_interventi").select("*").eq("ticket_id", tid).execute()
        if res_int and res_int.data:
            intervento = res_int.data[0]
    except Exception:
        pass

    if intervento:
        story.append(Paragraph("<b>Dettagli Intervento Tecnico:</b>", h2_style))
        
        desc_intervento = intervento.get("descrizione") or "Nessuna nota registrata."
        tecnico_intervento = intervento.get("tecnico") or ticket.get("assegnato_a") or "N/D"

        story.append(Paragraph(f"<b>Eseguito da:</b> {tecnico_intervento}", normal_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Descrizione lavoro:</b> {desc_intervento}", normal_style))
        story.append(Spacer(1, 12))

        # --- FIRMA (Salvata nel bucket "allegati") ---
        firma_path = intervento.get("firma_path")
        
        if firma_path:
            try:
                img_bytes = None
                if isinstance(firma_path, str) and firma_path.startswith("http"):
                    res = requests.get(firma_path, timeout=5)
                    if res.status_code == 200:
                        img_bytes = io.BytesIO(res.content)
                elif isinstance(firma_path, str):
                    # La firma si trova nel bucket "allegati" come visto in database.py
                    img_data = db.supabase.storage.from_("allegati").download(firma_path)
                    img_bytes = io.BytesIO(img_data)
                elif isinstance(firma_path, bytes):
                    img_bytes = io.BytesIO(firma_path)

                if img_bytes:
                    story.append(Paragraph("<b>Firma Intervento:</b>", normal_style))
                    story.append(Spacer(1, 6))
                    story.append(RLImage(img_bytes, width=180, height=70))
            except Exception as e:
                print(f"Errore caricamento firma PDF: {e}")

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
