import weasyprint  # Імпорт має бути ПІСЛЯ додавання шляху
import os
import jinja2
from io import BytesIO

# --- ФІКС ДЛЯ WINDOWS: Додаємо шлях до GTK3 вручну ---
gtk_path = r"C:\Program Files\GTK3-Runtime Win64\bin"

if os.path.exists(gtk_path):
    # Кажемо Python шукати DLL тут
    os.add_dll_directory(gtk_path)

    # Також додаємо в змінну середовища про всяк випадок
    os.environ['PATH'] = gtk_path + os.pathsep + os.environ.get('PATH', '')
else:
    print(
        f"⚠️ УВАГА: Не знайдено GTK3 за шляхом {gtk_path}. PDF може не працювати.")
# -----------------------------------------------------


class PDFService:
    def __init__(self):
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader("src/templates")
        )

    def generate_invoice_pdf(self, data: dict) -> BytesIO:
        template = self.template_env.get_template("invoice.html")
        html_content = template.render(
            invoice_number=data.get("number", "INV-001"),
            date=data.get("date"),
            client_name=data.get("client_name"),
            service_name=data.get("service_name"),
            amount=data.get("amount"),
            fop_name=data.get("fop_name", "ФОП Гиндич А.О.")
        )

        pdf_file = BytesIO()
        weasyprint.HTML(string=html_content).write_pdf(pdf_file)
        pdf_file.seek(0)
        return pdf_file
