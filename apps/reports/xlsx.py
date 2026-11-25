from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .services import Report

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _safe_title(text: str, used: set[str]) -> str:
    title = "".join(ch for ch in text if ch not in "[]:*?/\\")[:31] or "Sheet"
    base, n = title, 2
    while title in used:
        suffix = f" ({n})"
        title = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(title)
    return title


def report_to_xlsx(report: Report, school) -> bytes:
    wb = Workbook()
    cover = wb.active
    cover.title = "Report"
    lines = [
        "Republic of the Philippines",
        "Department of Education",
        school.region,
        school.division,
        school.name,
        f"School ID: {school.school_id}" if school.school_id else "",
        "",
        report.title,
        f"Period: {report.period_label}",
        report.description,
    ]
    for row, text in enumerate([line for line in lines if line is not None], start=1):
        cell = cover.cell(row=row, column=1, value=text)
        if text == report.title:
            cell.font = Font(bold=True, size=14)
    cover.column_dimensions["A"].width = 90

    used = {"Report"}
    for table in report.tables:
        ws = wb.create_sheet(_safe_title(table.title, used))
        ws.cell(row=1, column=1, value=table.title).font = Font(bold=True, size=12)
        if table.note:
            ws.cell(row=2, column=1, value=table.note).font = Font(italic=True, color="555555")
        header_row = 4
        for col, header in enumerate(table.headers, start=1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for r, values in enumerate(table.rows, start=header_row + 1):
            for c, value in enumerate(values, start=1):
                cell = ws.cell(row=r, column=c, value=value)
                cell.border = BORDER
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            if values and str(values[0]).startswith("Total"):
                for c in range(1, len(values) + 1):
                    ws.cell(row=r, column=c).font = Font(bold=True)
        for col in range(1, len(table.headers) + 1):
            width = max(
                [len(str(table.headers[col - 1]))]
                + [len(str(row[col - 1])) for row in table.rows if len(row) >= col]
            )
            ws.column_dimensions[get_column_letter(col)].width = min(max(width + 2, 10), 60)
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
