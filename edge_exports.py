"""Read-only, numbered export surfaces for public research data only."""
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
            ws.append([i] + [None if pd.isna(x) else x for x in row])
        ws.freeze_panes = "B2"
        out = BytesIO()
        wb.save(out)
        return out.getvalue()
    if fmt == "PDF":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from xml.sax.saxutils import escape
        out = BytesIO()
        doc = SimpleDocTemplate(out, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        columns = ["No."] + [str(x) for x in clean.columns]
        # Wide tables are summarized to avoid illegible, clipped PDF pages.
        columns = columns[:9]
        values = [columns]
        for i, row in enumerate(clean.itertuples(index=False, name=None), 1):
            values.append([str(i)] + [str(v)[:32] for v in row[:len(columns)-1]])
        table = Table(values, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F497D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        doc.build([Paragraph(escape(title) + " (PDF preview: first 8 fields)", styles["Heading2"]), table])
        return out.getvalue()
    raise ValueError("Unsupported export format")


def export_section(title, frame, key):
    """Expose CSV, full Excel and PDF preview with clear source labeling."""
    if frame is None or frame.empty:
        st.info(f"{title}: no data to export.")
        return
    slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    with st.expander(f"Download {title} · CSV / Excel / PDF", expanded=False):
        st.caption(f"{len(frame)} rows. CSV/Excel include all columns; PDF shows the first eight fields.")
        cols = st.columns(3)
        for col, fmt, ext, mime in zip(cols, ("CSV", "Excel", "PDF"),
                                   ("csv", "xlsx", "pdf"),
                                   ("text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/pdf")):
            col.download_button(fmt, export_bytes(frame, fmt, title),
                                file_name=f"edge_{slug}.{ext}", mime=mime,
                                key=f"export_{slug}_{ext}")


def render_export_center(snapshot_table, metadata, snapshot_fresh):
    st.subheader("Research Export Center")
    st.caption("Dated, research-only downloads. No certified trading signals or private journal exports.")
    if not metadata:
        st.warning("No validated snapshot available.")
        return
    st.caption(f"Snapshot session: {metadata.get('last_session', 'unknown')} | Fresh: {snapshot_fresh}")
    for title, dataset in (("Leadership ranks", "leadership"),
                           ("Current membership", "current_membership")):
        frame = snapshot_table(dataset)
        export_section(title, frame, dataset)
