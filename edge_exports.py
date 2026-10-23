"""Read-only, numbered export surfaces for research and owner-authorized data."""
from io import BytesIO
import re
import pandas as pd
import streamlit as st


def numbered(frame):
    """One-based display order; does not change frozen ranking columns."""
    result = frame.copy().reset_index(drop=True)
    result.index = pd.RangeIndex(1, len(result) + 1, name="No.")
    return result


def export_bytes(frame, fmt, title):
    clean = numbered(frame)
    if fmt in ('CSV', 'Excel'):
        def spreadsheet_safe(value):
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                return "'" + value
            return value
        clean = clean.map(spreadsheet_safe)
        clean.columns = [spreadsheet_safe(str(column)) for column in clean.columns]
    if fmt == "CSV":
        return clean.to_csv(index=True).encode("utf-8-sig")
    if fmt == "Excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = "Research"
        ws.append(["No."] + [str(c) for c in clean.columns])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F497D")
        for i, row in enumerate(clean.itertuples(index=False, name=None), 1):
            ws.append([i] + [None if x is None or (not isinstance(x, (list, dict, tuple)) and pd.isna(x)) else str(x) if isinstance(x, (list, dict, tuple)) else x for x in row])
        ws.freeze_panes = "B2"
        out = BytesIO()
        wb.save(out)
        return out.getvalue()
    if fmt == "PDF":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from xml.sax.saxutils import escape

        def printable(value):
            if value is None:
                return ""
            try:
                if bool(pd.isna(value)):
                    return ""
            except (TypeError, ValueError):
                pass
            return str(value)

        out = BytesIO()
        doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=24,
                                rightMargin=24, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle('ExportCell', parent=styles['Normal'], fontSize=6, leading=8, splitLongWords=True)
        story = [Paragraph(escape(str(title)), styles["Heading2"]),
                 Paragraph("Research export. Columns are split into labeled groups; all rows and fields are included.", styles["Normal"])]
        fields = [str(c) for c in clean.columns]
        for start_col in range(0, len(fields), 6):
            selected = list(range(start_col, min(start_col + 6, len(fields))))
            headers = ["No."] + [fields[i] for i in selected]
            values = [headers]
            for row_no, row in enumerate(clean.itertuples(index=False, name=None), 1):
                values.append([str(row_no)] + [printable(row[i]) for i in selected])
            widths = [34] + [(landscape(A4)[0] - 82) / len(selected)] * len(selected)
            values = [[Paragraph(escape(str(value)).replace('\n', '<br/>'), cell_style) for value in row] for row in values]
            table = Table(values, colWidths=widths, repeatRows=1, hAlign="LEFT", splitInRow=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F497D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]))
            if start_col:
                story.append(PageBreak())
            story.append(Paragraph(f"Fields {start_col + 1}–{start_col + len(selected)} of {len(fields)}", styles["Heading3"]))
            story.append(table)
        doc.build(story)
        return out.getvalue()
    raise ValueError("Unsupported export format")


def export_section(title, frame, key):
    """Expose CSV, full Excel and PDF preview with clear source labeling."""
    if frame is None or frame.empty:
        st.info(f"{title}: no data to export.")
        return
    slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    with st.expander(f"Download {title} · CSV / Excel / PDF", expanded=False):
        st.caption(f"{len(frame)} rows. CSV/Excel include all columns; PDF includes all fields in column groups.")
        fmt = st.selectbox('Export format', ('CSV', 'Excel', 'PDF'), key=f'export_format_{slug}')
        ext, mime = {'CSV': ('csv', 'text/csv'),
                     'Excel': ('xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                     'PDF': ('pdf', 'application/pdf')}[fmt]
        st.download_button(fmt, export_bytes(frame, fmt, title),
                           file_name=f"edge_{slug}.{ext}", mime=mime,
                           key=f"export_{slug}_{ext}")
