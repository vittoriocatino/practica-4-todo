"""Generate the two-page report plus annexes from verified real evidence."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/practica-4-todo-vittorio-catino.pdf"
NAVY = colors.HexColor("#173047")
BLUE = colors.HexColor("#247B9C")
LIGHT = colors.HexColor("#EDF5F8")
INK = colors.HexColor("#24394B")
MUTED = colors.HexColor("#526675")
W, H = letter
LEFT, RIGHT = 42, 570


def paragraph(c, content, y, size=10, leading=14, color=INK, x=LEFT, width=528):
    style = ParagraphStyle("body", fontName="Report", fontSize=size, leading=leading, textColor=color)
    p = Paragraph(content, style)
    _, h = p.wrap(width, 1000)
    p.drawOn(c, x, y - h)
    return y - h - 13


def header(c, title, page, total, draft=False):
    c.setFillColor(NAVY)
    c.rect(0, H - 75, W, 75, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("ReportBold", 18)
    c.drawString(LEFT, H - 33, ("BORRADOR: " if draft else "") + title)
    c.setFont("Report", 8.4)
    c.drawString(LEFT, H - 52, "Vittorio Catino | Desarrollo en la Nube | 18 de noviembre de 2026")
    c.setStrokeColor(colors.HexColor("#D4E2E9"))
    c.line(LEFT, 34, RIGHT, 34)
    c.setFillColor(MUTED)
    c.setFont("Report", 7)
    c.drawString(LEFT, 22, "Práctica 4 - To-Do List (CI/CD + Observabilidad)")
    c.drawRightString(RIGHT, 22, f"{page} / {total}")


def heading(c, text, y):
    c.setFillColor(BLUE)
    c.setFont("ReportBold", 11)
    c.drawString(LEFT, y, text)
    return y - 12


def box(c, x, y, w, h, title, subtitle):
    c.setFillColor(LIGHT)
    c.setStrokeColor(BLUE)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
    c.setFont("ReportBold", 8.5)
    c.setFillColor(NAVY)
    c.drawCentredString(x + w / 2, y + h - 16, title)
    c.setFont("Report", 7)
    c.drawCentredString(x + w / 2, y + 10, subtitle)


def arrow(c, x1, y1, x2, y2):
    import math
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.1)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    for delta in [-0.45, 0.45]:
        c.line(x2, y2, x2 - 6 * math.cos(angle + delta), y2 - 6 * math.sin(angle + delta))


def architecture(c, top):
    box(c, 42, top - 43, 148, 43, "GitHub Actions", "PR/CI -> tag -> Release ZIP")
    box(c, 224, top - 43, 147, 43, "EC2 + systemd", "Deploy SSM; user_data inicial")
    box(c, 405, top - 43, 165, 43, "RDS MySQL", "Privado; sólo SG de EC2")
    arrow(c, 190, top - 21, 224, top - 21)
    arrow(c, 371, top - 21, 405, top - 21)
    box(c, 42, top - 113, 148, 43, "Terraform + S3", "Estado cifrado + versionado")
    box(c, 224, top - 113, 147, 43, "Secrets Manager", "EC2: LabInstanceProfile")
    box(c, 405, top - 113, 165, 43, "CloudWatch -> SNS", "3 métricas / 3 alarmas / email")
    arrow(c, 116, top - 70, 246, top - 43)
    arrow(c, 298, top - 43, 298, top - 70)
    arrow(c, 354, top - 43, 435, top - 70)
    return top - 128


def main(draft=False):
    manifest = json.loads((ROOT / "evidence/manifest.json").read_text())
    required = ["provision", "destroy", "ci", "release", "deploy", "health", "sns_confirmed", "real_outage"]
    if not draft and not all(manifest.get(key) for key in required):
        raise RuntimeError("Refuse final report: required cloud verification is incomplete")
    annexes = manifest["screenshots"]
    if draft:
        annexes = [annex for annex in annexes if (ROOT / annex["file"]).is_file()]
    for annex in annexes:
        if not (ROOT / annex["file"]).is_file():
            raise FileNotFoundError(annex["file"])
        if not draft:
            for panel in annex.get("panels", []):
                if not (ROOT / panel["file"]).is_file():
                    raise FileNotFoundError(panel["file"])
    pdfmetrics.registerFont(TTFont("Report", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("ReportBold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
    pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold")
    destination = ROOT / "tmp/pdfs/layout-draft.pdf" if draft else OUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(destination), pagesize=letter)
    c.setTitle("Práctica 4 - To-Do List - Vittorio Catino")
    c.setAuthor("Vittorio Catino")
    total = 2 + len(annexes)
    header(c, "Práctica 4: To-Do List", 1, total, draft)
    y = heading(c, "Proyecto y arquitectura", H - 98)
    y = paragraph(c, "Se implementó una API FastAPI con persistencia en RDS MySQL y cuatro endpoints: <b>GET /tasks</b>, <b>POST /tasks</b>, <b>GET /version</b> y <b>GET /health</b>. Terraform administra EC2, Security Groups, Key Pair, RDS, secreto, SNS, alarmas y dashboard. El estado remoto reside en S3 privado, cifrado y versionado, con bloqueo nativo. EC2 lee las credenciales de RDS desde Secrets Manager en tiempo de ejecución usando LabInstanceProfile; no se guardan contraseñas en código ni en el entorno de la app.", y)
    y = architecture(c, y - 2)
    y = heading(c, "CI/CD y validación", y)
    y = paragraph(c, f"El PR ejecuta <b>{manifest['test_count']} pruebas</b> y lint; main exige el check tests aprobado. Se comprobó que CI fallido bloquea la integración y que, tras corregirlo, permite el merge. Un tag semántico genera un Release con ZIP y SHA-256; Deploy usa SSM para que EC2 descargue ese artefacto, cambie de versión y reinicie systemd. <b>/version confirmó {manifest['version']}</b>. Un workflow consulta /health cada cinco minutos y valida conexión, versión y timestamp. Provision y Destroy se ejecutaron manualmente desde Actions; user_data realiza la instalación inicial automáticamente.", y)
    y = heading(c, "1. Ventaja concreta de Terraform y relación con user_data / scp", y)
    y = paragraph(c, "Terraform permitió recrear de forma consistente la EC2, la RDS y sus dependencias sin repetir configuraciones en la consola. Hacer a mano la regla que permite MySQL únicamente desde el Security Group de la API, relacionarla con RDS y conservar los identificadores entre ejecuciones habría requerido más pasos y mayor riesgo de error. El plan hizo visibles los cambios y el estado remoto permitió destruir sólo los recursos de esta aplicación. Además, se identificó una restricción real del Learner Lab al consultar Object Lock durante el bootstrap del bucket y se adaptó la reutilización del backend existente.", y)
    y = paragraph(c, "Terraform declara y reconcilia infraestructura; user_data es el script de arranque que configura el sistema operativo, clona el repositorio e instala y levanta la aplicación. scp únicamente copiaría archivos a una máquina existente: no crea recursos ni registra sus dependencias. En esta solución no se necesitó SSH ni scp para preparar o actualizar EC2.", y)
    if y < 48:
        raise RuntimeError(f"Report page 1 overflow: {y}")
    c.showPage()
    header(c, "Reflexión y observabilidad", 2, total, draft)
    y = heading(c, "2. Pasos manuales eliminados y riesgos que evitó el pipeline", H - 98)
    y = paragraph(c, "El pipeline automatizó instalar dependencias para probar, ejecutar la suite, empaquetar el commit etiquetado, publicar el release, descargarlo en EC2, reiniciar el servicio y verificar qué versión quedó corriendo. Antes, repetir esos pasos manualmente podía producir un ZIP de otra rama, omitir una prueba, copiar archivos incompletos o reiniciar con una configuración equivocada. El artefacto del release y su hash permiten comprobar qué se despliega; la protección de main evita integrar pruebas fallidas y /version detecta una versión inesperada. El cambio de directorio mediante symlink reduce la ventana de actualización y el despliegue vuelve a la versión anterior si la comprobación de salud falla. Las credenciales temporales del lab deben renovarse al expirar; eso no se automatiza con claves permanentes.", y)
    y = heading(c, "Métricas, umbrales y acciones esperadas", y - 2)
    metrics = [
        ("CPUUtilization (nativa de AWS)", "Promedio >=80% durante 2 periodos de 60 s. Detecta saturación sostenida y reduce falsos positivos por picos breves. Acción: revisar carga, procesos y capacidad de EC2."),
        ("DatabaseErrors (boto3 / put_metric_data)", "Suma >=1 error en 60 s. Una operación fallida ya afecta al usuario; se emite 0 en operaciones correctas. Acción: revisar disponibilidad de RDS, conectividad, SG y secreto, y recuperar el servicio."),
        ("DatabaseLatency (boto3 / put_metric_data)", "Promedio >=500 ms durante 2 periodos de 60 s. Mide el tiempo de la operación de datos, incluida la conexión/verificación de esquema, para advertir degradación. Acción: correlacionar con CPU y errores, revisar conexiones y consultas."),
    ]
    for title, body in metrics:
        y = paragraph(c, f"<b>{title}.</b> {body}", y, size=9.1, leading=12.3)
    y = paragraph(c, "Cada métrica tiene una alarma independiente. Las tres publican transiciones ALARM y OK en el mismo tópico SNS, con la suscripción de <b>vittorio.catino@iteso.mx</b> confirmada. El dashboard muestra las tres series y sus umbrales. Los periodos y umbrales son valores iniciales de laboratorio, que se ajustarían con una línea base de tráfico real.", y, size=9.1, leading=12.3)
    y = heading(c, "3. Alarma elegida: errores de acceso a RDS", y - 2)
    y = paragraph(c, "Una situación real que la dispara es que RDS se detenga mientras la API intenta leer o escribir. Se validó deteniendo únicamente la RDS de la práctica y consultando /health; las operaciones fallaron con HTTP 503, la métrica DatabaseErrors aumentó y la alarma pasó a ALARM. No se forzó el estado de la alarma ni se publicaron errores simulados. Para diagnosticarlo, correlacionaría el incremento de errores con DatabaseLatency: si CPU permanece baja, el origen probable es la dependencia de datos, no saturación de EC2. Después revisaría el estado de RDS y las reglas de red. La solución aplicada fue iniciar RDS, esperar available y confirmar que /health volviera a OK; la recuperación también queda registrada.", y, size=9.1, leading=12.3)
    y = paragraph(c, "<b>Repositorio:</b> <link href='https://github.com/vittoriocatino/practica-4-todo' color='#247B9C'>github.com/vittoriocatino/practica-4-todo</link><br/><b>Evidencias:</b> anexos posteriores a estas dos páginas; historial de ejecuciones en Actions.<br/><b>Uso de IA:</b> se utilizó Codex para apoyar implementación, pruebas y documentación; las evidencias provienen de ejecuciones reales.", y, size=8, leading=10.5)
    if y < 48:
        raise RuntimeError(f"Report page 2 overflow: {y}")
    c.showPage()
    for i, annex in enumerate(annexes, start=3):
        header(c, annex["title"], i, total, draft)
        panels = annex.get("panels", [annex])
        if draft:
            panels = [panel for panel in panels if (ROOT / panel["file"]).is_file()]
        top = H - 105
        max_image_height = 550 if len(panels) == 1 else 160
        for panel in panels:
            image_path = ROOT / panel["file"]
            with Image.open(image_path) as img:
                iw, ih = img.size
            scale = min(528 / iw, max_image_height / ih)
            pw, ph = iw * scale, ih * scale
            c.drawImage(str(image_path), LEFT + (528 - pw) / 2, top - ph, width=pw, height=ph)
            top = paragraph(c, panel["caption"], top - ph - 12, size=8.6, leading=11.3)
        if top < 45:
            raise RuntimeError(f"Annex overflow: {annex['title']}")
        c.showPage()
    c.save()
    print(destination)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", action="store_true")
    main(parser.parse_args().draft)
