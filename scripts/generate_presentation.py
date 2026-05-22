from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import utils
import os
from PIL import Image

OUT = 'docs/demo_slides.pdf'
GIF = 'demos/admin_demo.gif'

slides = [
    {"title": "SHAPERS Academic Advisor", "bullets": ["AI-backed academic guidance for Indian students", "Admin pathway builder, Chat, Analytics", "Author: Your Name"]},
    {"title": "What It Does", "bullets": ["End-to-end pathway guidance (Class 11→PG)", "Provider-agnostic AIClient (OpenAI/Google/Dialogflow/Mock)", "Appointment booking, exports, analytics"]},
    {"title": "Admin Pathway Builder", "bullets": ["Select field, location, keywords", "Generates structured pathway JSON from AI", "Includes institutions, fees, salary outlook"]},
    {"title": "Live Chat", "bullets": ["Provider-agnostic chat with saved profile", "Export responses as text/PNG/PDF", "Analytics logging and sentiment"]},
    {"title": "Interaction Analytics", "bullets": ["Conversation volume, sentiment trends", "CSV export and downloadable reports", "Helps identify knowledge gaps"]},
    {"title": "Testing & QA", "bullets": ["Unit tests (pytest) and Playwright UI tests", "Conversational accuracy testing planned", "Demo assets included in repo"]},
    {"title": "Submission", "bullets": ["See SUBMISSION.md for evaluation checklist", "Demo GIF included: demos/admin_demo.gif", "Run scripts/demo_chat.py to reproduce"]},
    {"title": "Next Steps", "bullets": ["Professional analytics dashboard", "Improve sentiment accuracy and labeling", "Document architecture and API flow"]},
]

os.makedirs(os.path.dirname(OUT), exist_ok=True)

c = canvas.Canvas(OUT, pagesize=landscape(A4))
width, height = landscape(A4)

# If GIF exists, convert first frame to PNG for embedding
png_for_embed = None
if os.path.exists(GIF):
    try:
        im = Image.open(GIF)
        im.seek(0)
        tmp = 'demos/_gif_preview.png'
        im.convert('RGB').save(tmp, 'PNG')
        png_for_embed = tmp
    except Exception:
        png_for_embed = None

for idx, s in enumerate(slides, 1):
    c.setFont('Helvetica-Bold', 28)
    c.drawString(2*cm, height - 2.5*cm, s['title'])
    c.setFont('Helvetica', 14)
    y = height - 4*cm
    for b in s['bullets']:
        c.drawString(2*cm, y, u'• ' + b)
        y -= 1*cm
    # On slide 7, embed GIF preview if available
    if idx == 7 and png_for_embed and os.path.exists(png_for_embed):
        try:
            img = utils.ImageReader(png_for_embed)
            iw, ih = img.getSize()
            maxw = width/3
            ratio = min(maxw/iw, (height/2)/ih)
            w = iw * ratio
            h = ih * ratio
            c.drawImage(png_for_embed, width - w - 2*cm, height - h - 2*cm, width=w, height=h)
        except Exception:
            pass
    c.showPage()

c.save()
print('Presentation generated at', OUT)
