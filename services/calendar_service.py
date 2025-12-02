from datetime import date, timedelta


def shift_to_workday(d: date) -> date:
    """Если дата попадает на субботу/воскресенье — сдвигаем на понедельник."""
    if d.weekday() == 5:      # Saturday
        return d + timedelta(days=2)
    if d.weekday() == 6:      # Sunday
        return d + timedelta(days=1)
    return d


class TaxCalendarService:
    @staticmethod
    def get_monthly_ep_deadlines(year: int):
        deadlines = []
        for month in range(1, 13):
            # период, за который платим
            period_month = month
            period_year = year

            # месяц, до 20-го которого нужно оплатить (следующий месяц)
            pay_month = month + 1
            pay_year = year
            if pay_month == 13:
                pay_month = 1
                pay_year = year + 1

            pay_until = date(pay_year, pay_month, 20)
            pay_until = shift_to_workday(pay_until)

            deadlines.append(
                {
                    "type": "ЄП",
                    "period": f"{period_month:02d}.{period_year}",  # 01.2026
                    "deadline": pay_until.isoformat(),              # 2026-02-20
                }
            )
        return deadlines

    @staticmethod
    def get_quarterly_esv_deadlines(year: int):
        deadlines = []
        quarters = {
            1: date(year, 4, 20),
            2: date(year, 7, 20),
            3: date(year, 10, 20),
            4: date(year + 1, 1, 20),
        }
        for q, raw_date in quarters.items():
            deadlines.append(
                {
                    "type": "ЄСВ",
                    "quarter": q,
                    "deadline": shift_to_workday(raw_date).isoformat(),
                }
            )
        return deadlines

    @staticmethod
    def get_declaration_deadlines(year: int):
        deadlines = []
        quarters = {
            1: date(year, 5, 10),
            2: date(year, 8, 9),
            3: date(year, 11, 9),
            4: date(year + 1, 2, 9),
        }
        for q, raw_date in quarters.items():
            deadlines.append(
                {
                    "type": "Декларація 3 групи",
                    "quarter": q,
                    "deadline": shift_to_workday(raw_date).isoformat(),
                }
            )
        return deadlines

