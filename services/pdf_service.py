# services/pdf_service.py
from fastapi import HTTPException
from io import BytesIO
from datetime import datetime
from textwrap import wrap
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from PIL import Image, ImageDraw, ImageFont


class PDFService:
    @staticmethod
    def _fallback_pdf(html: str, context: dict | None = None) -> bytes:
        """
        Простий PDF без зовнішніх залежностей (Pillow).
        Рендерить текстом частину HTML, щоб файл був доступний в архіві.
        """
        img = Image.new("RGB", (1240, 1754), "white")  # ~A4 @ 150dpi
        draw = ImageDraw.Draw(img)
        lines = [
            "FOPilot PDF (fallback)",
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "",
        ]

        if context:
            lines += [
                f"ПІБ: {context.get('full_name', '')}",
                f"ІПН: {context.get('tax_id', '')}",
                f"Період: {context.get('period_text', '')}",
                f"Дохід: {context.get('total_income', '')}",
                f"ЄП: {context.get('single_tax', '')}",
                f"Дата заповнення: {context.get('filled_date', '')}",
                "",
                "Дані подані у спрощеному вигляді, бо WeasyPrint недоступний.",
                "",
            ]

        if html:
            lines.append("HTML (обрізано):")
            lines += wrap((html or "")[:800], width=90)

        text = "\n".join(lines)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.multiline_text((40, 40), text, fill="black", font=font, spacing=4)

        buf = BytesIO()
        img.save(buf, format="PDF", resolution=150.0)
        return buf.getvalue()

    @staticmethod
    def html_to_pdf(html: str, base_path: str | None = None, context: dict | None = None) -> bytes:
        return PDFService._fallback_pdf(html, context=context)

    @staticmethod
    def render_declaration_flat(context: dict) -> bytes:
        """
        Спрощена, але візуально максимально «офіційна» декларація
        у вигляді заповненої форми без WeasyPrint (Pillow + текст/таблиці).
        """
        # A4 @ 300dpi
        width, height = 2480, 3508
        margin_x, margin_y = 160, 220

        def load_font(size: int, bold: bool = False):
            try:
                candidates = []
                if bold:
                    candidates += [
                        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
                        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                        Path("/Library/Fonts/Arial Unicode.ttf"),
                        Path("/Library/Fonts/Arial Bold.ttf"),
                    ]
                else:
                    candidates += [
                        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
                        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                        Path("/Library/Fonts/Arial Unicode.ttf"),
                        Path("/Library/Fonts/Arial.ttf"),
                    ]

                font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
                candidates += [
                    Path(ImageFont.__file__).resolve().parent / font_name,
                    Path(ImageFont.__file__).resolve().parent / "fonts" / font_name,
                ]

                for p in candidates:
                    if p.exists():
                        return ImageFont.truetype(str(p), size)
                return ImageFont.truetype(font_name, size)
            except Exception:
                return ImageFont.load_default()

        font_title = load_font(50, bold=True)
        font_bold = load_font(42, bold=True)
        font_regular = load_font(36, bold=False)
        font_small = load_font(28, bold=False)
        font_small_bold = load_font(30, bold=True)

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        def measure(text: str, font) -> tuple[int, int]:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                return font.getsize(text)

        def to_decimal(value) -> Decimal:
            try:
                return Decimal(str(value).replace(" ", "").replace(",", "."))
            except Exception:
                return Decimal("0.00")

        def money(value) -> str:
            try:
                dec = to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return format(dec, "f")
            except Exception:
                return "0.00"

        # ---- Числові значення ----
        total_income_val = to_decimal(context.get("total_income", 0))
        single_tax_val = to_decimal(context.get("single_tax", 0))
        esv_val = to_decimal(context.get("esv", 0))
        total_due_val = context.get("total_due")
        if total_due_val is None:
            total_due_val = single_tax_val + esv_val
        else:
            total_due_val = to_decimal(total_due_val)

        total_income = money(total_income_val)
        single_tax = money(single_tax_val)
        esv = money(esv_val)
        total_due = money(total_due_val)

        tax_rate = context.get("tax_rate")
        if tax_rate is None:
            if total_income_val > 0:
                try:
                    rate = (single_tax_val / total_income_val * Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    tax_rate = format(rate, "f").rstrip("0").rstrip(".")
                except Exception:
                    tax_rate = "5"
            else:
                tax_rate = "5"
        tax_rate_str = str(tax_rate)

        year = context.get("year", "")
        quarter_raw = context.get("quarter")
        try:
            quarter_int = int(quarter_raw)
        except (TypeError, ValueError):
            quarter_int = None
        quarter_text = context.get("quarter_text")
        if not quarter_text:
            roman = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(quarter_int, quarter_raw or "")
            if year and roman:
                quarter_text = f"{roman} квартал {year} року"
            elif roman:
                quarter_text = f"{roman} квартал"
            else:
                quarter_text = ""

        # ---------------- ШАПКА ----------------
        y = margin_y

        # Лівий верхній блок "Відмітка про одержання"
        stamp_w, stamp_h = 620, 260
        stamp_x1, stamp_y1 = margin_x, y - 60
        stamp_x2, stamp_y2 = stamp_x1 + stamp_w, stamp_y1 + stamp_h
        draw.rectangle((stamp_x1, stamp_y1, stamp_x2, stamp_y2), outline="black", width=2)
        stamp_lines = [
            "Відмітка про одержання",
            "(штамп контролюючого органу,",
            "дата, вхідний номер)",
        ]
        sy = stamp_y1 + 28
        for line in stamp_lines:
            draw.text((stamp_x1 + 24, sy), line, fill="black", font=font_small)
            sy += measure(line, font_small)[1] + 2

        # Правий верхній блок "ЗАТВЕРДЖЕНО"
        approved_lines = [
            ("ЗАТВЕРДЖЕНО", font_small_bold),
            ("Наказ Міністерства фінансів України", font_small),
            ("19 червня 2015 року № 578", font_small),
            ("(у редакції наказу Міністерства фінансів України", font_small),
            ("від 31 січня 2025 року № 57)", font_small),
        ]
        right_block_width = 0
        line_spacing = 4
        for text, font in approved_lines:
            w, h = measure(text, font)
            right_block_width = max(right_block_width, w)
        block_x = width - margin_x - right_block_width
        block_y = stamp_y1
        cur_y = block_y
        for text, font in approved_lines:
            w, h = measure(text, font)
            draw.text((block_x, cur_y), text, fill="black", font=font)
            cur_y += h + line_spacing
        block_bottom = cur_y

        # Порядковий № за рік — праворуч під шапкою
        ordinal_label = "Порядковий № за рік*"
        ow, oh = measure(ordinal_label, font_small)
        ordinal_x = width - margin_x - right_block_width
        ordinal_y = block_bottom + 30
        draw.text((ordinal_x, ordinal_y), ordinal_label, fill="black", font=font_small)
        box_y1 = ordinal_y + oh + 6
        box_y2 = box_y1 + 46
        box_x1 = ordinal_x
        box_x2 = ordinal_x + 260
        draw.rectangle((box_x1, box_y1, box_x2, box_y2), outline="black", width=2)

        # Заголовок декларації
        title_line1 = "Податкова декларація платника єдиного податку третьої групи"
        title_line2 = "(фізична особа-підприємець)"
        title_y = block_bottom + 130

        tw1, th1 = measure(title_line1, font_title)
        draw.text(((width - tw1) / 2, title_y), title_line1, fill="black", font=font_title)

        tw2, th2 = measure(title_line2, font_regular)
        draw.text(((width - tw2) / 2, title_y + th1 + 12), title_line2, fill="black", font=font_regular)

        y = title_y + th1 + th2 + 80

        # Тип декларації
        type_text = "Тип податкової декларації:"
        draw.text((margin_x, y), type_text, fill="black", font=font_regular)
        tx, th = measure(type_text, font_regular)
        cb_x = margin_x + tx + 30
        cb_size = 40
        cb_gap = 30

        def checkbox(x, label: str, checked: bool = False):
            nonlocal cb_x
            y_top = y - 6
            draw.rectangle((x, y_top, x + cb_size, y_top + cb_size), outline="black", width=2)
            if checked:
                draw.line((x + 8, y_top + 20, x + 18, y_top + 30), fill="black", width=3)
                draw.line((x + 18, y_top + 30, x + 32, y_top + 10), fill="black", width=3)
            draw.text((x + cb_size + 10, y_top + 4), label, fill="black", font=font_regular)
            w, _ = measure(label, font_regular)
            cb_x = x + cb_size + 10 + w + cb_gap

        checkbox(cb_x, "звітна", checked=True)
        checkbox(cb_x, "звітна нова", checked=False)
        checkbox(cb_x, "уточнююча", checked=False)

        y += th + 50

        # ---------------- РОЗДІЛ I ----------------
        def draw_line(text: str, font, extra_y: int = 0):
            nonlocal y
            y += extra_y
            draw.text((margin_x, y), text, fill="black", font=font)
            y += measure(text, font)[1] + 6

        draw_line("I. Загальні відомості", font_bold)
        draw_line(f"Прізвище, ім'я, по батькові: {context.get('full_name', '')}", font_regular)
        draw_line(
            f"Реєстраційний номер облікової картки платника податків: {context.get('tax_id', '')}",
            font_regular,
        )
        draw_line(f"Звітний (податковий) період: {quarter_text}", font_regular)
        draw_line(f"Дата заповнення: {context.get('filled_date', '')}", font_regular)

        y += 60

        # ---------------- РОЗДІЛ II ----------------
        draw_line("II. Дохід, що підлягає оподаткуванню", font_bold, extra_y=0)
        y += 40  # додатковий відступ перед таблицею

        def draw_table(start_y: int, rows: list[tuple[str, str]]) -> int:
            table_width = width - margin_x * 2
            col_split = margin_x + int(table_width * 0.70)

            header_h = 90
            row_h = 90
            x1, x2 = margin_x, margin_x + table_width

            draw.rectangle((x1, start_y, x2, start_y + header_h),
                           outline="black", fill=(240, 240, 240), width=2)
            draw.line((col_split, start_y, col_split, start_y + header_h), fill="black", width=2)
            draw.text((x1 + 22, start_y + 26), "Показник", fill="black", font=font_bold)
            draw.text((col_split + 22, start_y + 26), "Сума, грн", fill="black", font=font_bold)

            cur_y = start_y + header_h
            for label, amount in rows:
                draw.rectangle((x1, cur_y, x2, cur_y + row_h), outline="black", width=2)
                draw.line((col_split, cur_y, col_split, cur_y + row_h), fill="black", width=2)
                draw.text((x1 + 22, cur_y + 24), label, fill="black", font=font_regular)
                aw, ah = measure(amount, font_regular)
                draw.text((x2 - aw - 22, cur_y + 24), amount, fill="black", font=font_regular)
                cur_y += row_h
            return cur_y

        rows_income = [
            ("1. Сума доходу за податковий (звітний) період", total_income),
            ("2. Сума доходу, що перевищує граничний обсяг доходу", ""),
            ("3. Сума доходу від іншої діяльності (за іншими ставками)", ""),
            ("4. Сума доходу, що не є об’єктом оподаткування", ""),
        ]
        y = draw_table(y, rows_income)

        y += 70

        # ---------------- РОЗДІЛ III ----------------
        draw_line("III. Розрахунок податкових зобов'язань з єдиного податку", font_bold, extra_y=0)
        y += 40  # додатковий відступ перед другою таблицею

        rows_tax = [
            ("20. Ставка єдиного податку (%)", tax_rate_str),
            ("21. Сума нарахованого єдиного податку", single_tax),
            ("30. ЄСВ за себе", esv),
            ("31. ЄСВ за найманих працівників", "0.00"),
            ("40. Загальна сума до сплати", total_due),
        ]
        y = draw_table(y, rows_tax)

        # Примітки дрібним шрифтом
        y += 30
        notes = [
            "* С – відсоткова ставка єдиного податку, що застосовується платником залежно від обраної групи платника єдиного податку.",
            "** У рядках 30–31 зазначаються суми єдиного внеску (ЄСВ), сплачені за себе та найманих працівників.",
        ]
        for n in notes:
            draw.text((margin_x, y), n, fill="black", font=font_small)
            y += measure(n, font_small)[1] + 4

        y += 80

        # Підпис платника
        draw.text((margin_x, y), f"«___» __________ {year} р.", fill="black", font=font_regular)
        y += measure("X", font_regular)[1] + 24
        signature = f"Платник податку / уповноважена особа: ______________________ ({context.get('full_name', '')})"
        draw.text((margin_x, y), signature, fill="black", font=font_regular)

        # ---------------- БЛОК КОНТРОЛЮЮЧОГО ОРГАНУ ----------------
        y += 150
        ctrl_title = "Ця частина заповнюється посадовою особою контролюючого органу"
        draw.text((margin_x, y), ctrl_title, fill="black", font=font_small_bold)
        y += measure(ctrl_title, font_small_bold)[1] + 18

        ctrl_lines = [
            "Відмітка про внесення даних до електронної бази податкової звітності: «___» __________ 20__ року",
            "Посадова особа контролюючого органу ____________________ (підпис, П.І.Б.)",
            "",
            "За результатами камеральної перевірки:",
            "Порушень (помилок) не виявлено [   ]      Виявлено порушення (помилки) [   ]",
            "Складено акт від «___» __________ 20__ року № _________",
        ]
        for line in ctrl_lines:
            draw.text((margin_x, y), line, fill="black", font=font_small)
            y += measure(line, font_small)[1] + 6

        buf = BytesIO()
        img.save(buf, format="PDF", resolution=300.0)
        return buf.getvalue()
