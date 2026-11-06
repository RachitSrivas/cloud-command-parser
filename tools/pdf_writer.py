"""Pure Python PDF Generator with Page Layout, Flowables, Tables, and Formatting.
No external dependencies. Produces standard compliant PDF 1.4 documents.
"""

import os
import re

class PDFDoc:
    def __init__(self, filename="document.pdf", page_width=612, page_height=792, margin=54):
        self.filename = filename
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.usable_width = page_width - 2 * margin
        self.pages = []
        self.current_stream = []
        self.y = page_height - margin
        self.page_num = 1
        self.header_text = ""
        self.title_text = ""

    def new_page(self):
        if self.current_stream:
            self.pages.append(self.current_stream)
        self.current_stream = []
        self.page_num += 1
        self.y = self.page_height - self.margin
        self._draw_page_decorations()

    def _draw_page_decorations(self):
        # Header (pages > 1)
        if self.page_num > 1 and self.header_text:
            self.current_stream.append(
                f"BT /F1 9 Tf 0.4 0.4 0.4 rg {self.margin} {self.page_height - 36} Td ({self.escape(self.header_text)}) Tj ET"
            )
            # Thin header rule
            self.current_stream.append(
                f"0.8 0.8 0.8 RG 0.5 w {self.margin} {self.page_height - 42} m {self.page_width - self.margin} {self.page_height - 42} l S"
            )

        # Footer (page number)
        footer_str = f"Page {self.page_num}"
        self.current_stream.append(
            f"BT /F1 9 Tf 0.4 0.4 0.4 rg {self.page_width - self.margin - 40} 36 Td ({footer_str}) Tj ET"
        )
        # Footer rule
        self.current_stream.append(
            f"0.8 0.8 0.8 RG 0.5 w {self.margin} 48 m {self.page_width - self.margin} 48 l S"
        )

    def check_space(self, height):
        if self.y - height < self.margin + 20:
            self.new_page()

    def escape(self, text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def add_title(self, title, subtitle="", author=""):
        self._draw_page_decorations()
        self.current_stream.append(
            f"BT /F2 20 Tf 0.08 0.18 0.36 rg {self.margin} {self.y} Td ({self.escape(title)}) Tj ET"
        )
        self.y -= 26
        if subtitle:
            self.current_stream.append(
                f"BT /F1 12 Tf 0.25 0.32 0.42 rg {self.margin} {self.y} Td ({self.escape(subtitle)}) Tj ET"
            )
            self.y -= 18
        if author:
            self.current_stream.append(
                f"BT /F3 10 Tf 0.4 0.4 0.4 rg {self.margin} {self.y} Td ({self.escape(author)}) Tj ET"
            )
            self.y -= 22
        # Title separator rule
        self.current_stream.append(
            f"0.12 0.32 0.58 RG 1.5 w {self.margin} {self.y + 10} m {self.page_width - self.margin} {self.y + 10} l S"
        )
        self.y -= 10

    def add_heading1(self, text):
        self.check_space(40)
        self.y -= 14
        self.current_stream.append(
            f"BT /F2 13 Tf 0.10 0.22 0.45 rg {self.margin} {self.y} Td ({self.escape(text)}) Tj ET"
        )
        self.y -= 6
        self.current_stream.append(
            f"0.7 0.75 0.85 RG 0.75 w {self.margin} {self.y} m {self.page_width - self.margin} {self.y} l S"
        )
        self.y -= 14

    def add_heading2(self, text):
        self.check_space(30)
        self.y -= 10
        self.current_stream.append(
            f"BT /F2 11 Tf 0.15 0.28 0.40 rg {self.margin} {self.y} Td ({self.escape(text)}) Tj ET"
        )
        self.y -= 14

    def add_paragraph(self, text, font_size=9.5, leading=13.5, color="0 0 0"):
        words = text.split()
        lines = []
        cur_line = []
        cur_len = 0
        max_chars = int(self.usable_width / (font_size * 0.52))

        for w in words:
            if cur_len + len(w) + 1 <= max_chars:
                cur_line.append(w)
                cur_len += len(w) + 1
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
        if cur_line:
            lines.append(" ".join(cur_line))

        for line in lines:
            self.check_space(leading)
            self.current_stream.append(
                f"BT /F1 {font_size} Tf {color} rg {self.margin} {self.y} Td ({self.escape(line)}) Tj ET"
            )
            self.y -= leading
        self.y -= 4

    def add_bullet(self, bold_prefix, text, font_size=9.2, leading=13):
        self.check_space(leading + 2)
        # Bullet dot
        self.current_stream.append(
            f"BT /F2 {font_size} Tf 0.12 0.32 0.58 rg {self.margin + 4} {self.y} Td (\x95) Tj ET"
        )
        prefix_len = len(bold_prefix) * 5.2
        self.current_stream.append(
            f"BT /F2 {font_size} Tf 0.1 0.1 0.1 rg {self.margin + 16} {self.y} Td ({self.escape(bold_prefix)}) Tj ET"
        )
        
        words = text.split()
        lines = []
        cur_line = []
        cur_len = 0
        max_chars = int((self.usable_width - 24 - prefix_len) / (font_size * 0.50))
        first_line = True

        for w in words:
            limit = max_chars if first_line else int((self.usable_width - 24) / (font_size * 0.50))
            if cur_len + len(w) + 1 <= limit:
                cur_line.append(w)
                cur_len += len(w) + 1
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
                first_line = False
        if cur_line:
            lines.append(" ".join(cur_line))

        for idx, line in enumerate(lines):
            if idx == 0:
                self.current_stream.append(
                    f"BT /F1 {font_size} Tf 0 0 0 rg {self.margin + 16 + prefix_len} {self.y} Td ({self.escape(line)}) Tj ET"
                )
            else:
                self.check_space(leading)
                self.y -= leading
                self.current_stream.append(
                    f"BT /F1 {font_size} Tf 0 0 0 rg {self.margin + 16} {self.y} Td ({self.escape(line)}) Tj ET"
                )
        self.y -= leading

    def add_table(self, headers, rows, col_widths=None):
        num_cols = len(headers)
        if not col_widths:
            w = self.usable_width / num_cols
            col_widths = [w] * num_cols

        row_height = 18
        table_height = (len(rows) + 1) * row_height
        self.check_space(min(table_height + 10, 120))

        # Header background
        header_y = self.y - row_height
        self.current_stream.append(
            f"0.90 0.93 0.97 rg {self.margin} {header_y} {self.usable_width} {row_height} re f"
        )
        # Header borders
        self.current_stream.append(
            f"0.7 0.75 0.85 RG 0.75 w {self.margin} {header_y} {self.usable_width} {row_height} re S"
        )
        # Header texts
        cur_x = self.margin + 6
        for i, h in enumerate(headers):
            self.current_stream.append(
                f"BT /F2 8.5 Tf 0.1 0.2 0.35 rg {cur_x} {header_y + 5} Td ({self.escape(str(h))}) Tj ET"
            )
            cur_x += col_widths[i]

        self.y = header_y

        for r_idx, row in enumerate(rows):
            self.check_space(row_height)
            cur_y = self.y - row_height
            # Alternate row background
            if r_idx % 2 == 1:
                self.current_stream.append(
                    f"0.98 0.98 0.99 rg {self.margin} {cur_y} {self.usable_width} {row_height} re f"
                )
            self.current_stream.append(
                f"0.85 0.85 0.88 RG 0.5 w {self.margin} {cur_y} {self.usable_width} {row_height} re S"
            )
            cur_x = self.margin + 6
            for i, cell in enumerate(row):
                self.current_stream.append(
                    f"BT /F1 8.2 Tf 0.1 0.1 0.1 rg {cur_x} {cur_y + 5} Td ({self.escape(str(cell))}) Tj ET"
                )
                cur_x += col_widths[i]
            self.y = cur_y
        self.y -= 10

    def add_code_block(self, code_lines):
        line_height = 12
        box_height = len(code_lines) * line_height + 12
        self.check_space(box_height)
        box_y = self.y - box_height
        # Gray background
        self.current_stream.append(
            f"0.95 0.95 0.96 rg {self.margin} {box_y} {self.usable_width} {box_height} re f"
        )
        self.current_stream.append(
            f"0.82 0.82 0.85 RG 0.5 w {self.margin} {box_y} {self.usable_width} {box_height} re S"
        )
        text_y = box_y + box_height - 12
        for cl in code_lines:
            self.current_stream.append(
                f"BT /F4 8 Tf 0.15 0.15 0.15 rg {self.margin + 8} {text_y} Td ({self.escape(cl)}) Tj ET"
            )
            text_y -= line_height
        self.y = box_y - 8

    def save(self):
        if self.current_stream:
            self.pages.append(self.current_stream)

        os.makedirs(os.path.dirname(os.path.abspath(self.filename)), exist_ok=True)

        objects = []
        # 1: Catalog
        # 2: Pages
        # 3: Helvetica, 4: Helvetica-Bold, 5: Helvetica-Oblique, 6: Courier
        num_pages = len(self.pages)
        page_obj_ids = [7 + i * 2 for i in range(num_pages)]
        content_obj_ids = [8 + i * 2 for i in range(num_pages)]

        # Fonts
        font_f1 = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        font_f2 = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        font_f3 = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"
        font_f4 = "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"

        font_res = "<< /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >>"

        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        catalog_obj = f"<< /Type /Catalog /Pages 2 0 R >>"
        pages_obj = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>"

        objects.append(catalog_obj)      # 1
        objects.append(pages_obj)        # 2
        objects.append(font_f1)          # 3
        objects.append(font_f2)          # 4
        objects.append(font_f3)          # 5
        objects.append(font_f4)          # 6

        for i in range(num_pages):
            page_stream = "\n".join(self.pages[i])
            stream_bytes = page_stream.encode("latin-1", "replace")
            page_obj = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width} {self.page_height}] /Resources {font_res} /Contents {content_obj_ids[i]} 0 R >>"
            content_obj = f"<< /Length {len(stream_bytes)} >>\nstream\n{page_stream}\nendstream"
            objects.append(page_obj)
            objects.append(content_obj)

        # Output PDF binary
        out = bytearray()
        out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj_content in enumerate(objects, 1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n{obj_content}\nendobj\n".encode("latin-1", "replace"))

        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets:
            out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

        trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        out.extend(trailer.encode("latin-1"))

        with open(self.filename, "wb") as f:
            f.write(out)
        print(f"Generated {self.filename} ({num_pages} pages, {len(out)} bytes)")
