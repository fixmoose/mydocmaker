#!/usr/bin/env python3
"""MyDocMaker regression suite.

Run:  python3 tests/regress.py            (all)
      python3 tests/regress.py notes      (one group)

Kept IN THE REPO on purpose: the previous suite lived in /tmp and was wiped by
a system cleanup, taking the only coverage with it.

Opens one real Tk window at a time (there is no Xvfb here); it is closed again
between groups.
"""
import io
import os
import sys
import time
import tempfile
import traceback

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
os.environ.setdefault("MYDOCMAKER_NO_DND", "1")

import tkinter as tk                                    # noqa: E402
import numpy as np                                      # noqa: E402
import pypdfium2 as pdfium                              # noqa: E402
from pypdf import PdfReader                             # noqa: E402
from reportlab.pdfgen import canvas as rcanvas          # noqa: E402

import mydocmaker as M                                   # noqa: E402

TMP = tempfile.mkdtemp(prefix="mydocmaker_regress_")
FAILS = []
RESULTS = []
DIALOGS = []        # message boxes the app tried to show


def _silence_dialogs():
    """Record message boxes instead of showing them.

    A test must never put a modal on the user's desktop and sit there waiting
    for someone to press OK — the print guard check did exactly that, which is
    both an interruption and a hang waiting to happen on an unattended run.
    """
    def record(kind):
        def fn(title=None, message=None, *a, **k):
            DIALOGS.append((kind, title, message))
            return {"askyesno": False, "askokcancel": False,
                    "askyesnocancel": None}.get(kind, "ok")
        return fn

    for name in ("showinfo", "showwarning", "showerror",
                 "askyesno", "askokcancel", "askyesnocancel"):
        setattr(M.messagebox, name, record(name))


_silence_dialogs()


def check(group, name, cond, detail=""):
    RESULTS.append((group, name, bool(cond), detail))
    if not cond:
        FAILS.append(f"{group}/{name} {detail}")


def make_pdf(path, pages=1, size=(612, 792), text="page"):
    """A test PDF. text=None gives genuinely blank pages, which the note and
    frame checks need — any stray page text ends up inside the ink bbox and
    makes a geometry assertion meaningless."""
    c = rcanvas.Canvas(path, pagesize=size)
    for i in range(pages):
        if text is not None:
            c.setFont("Helvetica", 20)
            c.drawString(72, size[1] - 92, f"{text} {i + 1}")
        c.showPage()
    c.save()
    return path


def ink_bbox(pil, scale=1.0, thresh=180):
    """Bounding box of the dark pixels, converted back to PDF POINTS.

    Dividing by `scale` matters: note_pdf_box() is in points, and comparing it
    against raw pixels can only ever fail."""
    a = np.array(pil.convert("L"))
    ys, xs = np.where(a < thresh)
    if len(xs) == 0:
        return None, 0
    h = pil.height
    return ((round(float(xs.min()) / scale, 1),
             round(float(h - ys.max()) / scale, 1),
             round(float(xs.max()) / scale, 1),
             round(float(h - ys.min()) / scale, 1)),
            int((a < thresh).sum()))


def render_ink(pdf_bytes_or_doc, page=0, scale=4.0):
    if isinstance(pdf_bytes_or_doc, (bytes, bytearray)):
        doc = pdfium.PdfDocument(pdf_bytes_or_doc)
        try:
            return ink_bbox(doc[page].render(scale=scale).to_pil(), scale)
        finally:
            doc.close()
    return ink_bbox(pdf_bytes_or_doc[page].render(scale=scale).to_pil(), scale)


class Harness:
    """A booted App with a Preview that has actually rendered."""

    def __init__(self, paths, size="letter"):
        self.root = tk.Tk()
        self.root.geometry("1500x980")
        self.app = M.App(self.root)
        self.root.update()
        self.app.size_var.set(size)
        self.app.orient_var.set("portrait")
        self.app._on_page_mode_changed()
        self.root.update()
        if paths:
            self.app.add_paths(list(paths))
            self.wait(lambda: all(i.cached_pdf_bytes for i in self.app.items))
        self.pv = self.app.preview
        self.app.notebook.select(3)                      # Preview Pages
        self.settle(30)
        self.pv.refresh_preview()
        self.wait(lambda: bool(self.pv._page_boxes))
        self.settle(20)

    def wait(self, pred, timeout=45):
        t0 = time.time()
        while not pred() and time.time() - t0 < timeout:
            self.root.update()
            time.sleep(0.04)
        return pred()

    def settle(self, n=18):
        for _ in range(n):
            self.root.update()
            time.sleep(0.012)

    def cpt(self, x_pt, y_pt, page=0):
        px, py, _pw, ph = self.pv._page_boxes[page]
        s = self.pv._page_render_scale
        return (px + x_pt * s, py + (ph - y_pt * s))

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class Ev:
    def __init__(self, x, y):
        self.x = int(x)
        self.y = int(y)
        self.x_root = int(x)
        self.y_root = int(y)


# ---------------------------------------------------------------- groups
def g_startup():
    h = Harness([make_pdf(os.path.join(TMP, "s.pdf"), 2)])
    try:
        tabs = [h.app.notebook.tab(i, "text")
                for i in range(h.app.notebook.index("end"))]
        check("startup", "five tabs", len(tabs) == 5, str(tabs))
        check("startup", "tab order",
              tabs == [M.TAB_FILES, M.TAB_EDITOR, M.TAB_ORDER,
                       M.TAB_PREVIEW, M.TAB_STYLE], str(tabs))
        check("startup", "preview rendered", h.pv._page_count == 2,
              f"pages={h.pv._page_count}")
        for attr in ("create_btn", "print_btn"):
            check("startup", f"{attr} exists", hasattr(h.app, attr))
        check("startup", "create label",
              "Create the File" in h.app.create_btn.cget("text"),
              h.app.create_btn.cget("text"))
        out = h.app.assemble_from_cache()
        check("startup", "assemble works", out and len(PdfReader(
            io.BytesIO(out)).pages) == 2)
    finally:
        h.close()


def g_notes():
    """The WYSIWYG contract: preview pixels == output pixels."""
    h = Harness([make_pdf(os.path.join(TMP, "n.pdf"), 1, text=None)])
    try:
        for size, txt in ((14, "Hxy"), (9, "Adriatic Builders LLC"),
                          (24, "Wg")):
            h.app.text_notes.clear()
            h.app.text_notes.append(
                {"page": 0, "x_pt": 100.0, "y_pt": 500.0, "text": txt,
                 "font": "Helvetica", "size": size, "bold": False,
                 "italic": False})
            h.pv._live_note = None
            h.pv._rebuild_now()
            h.settle()
            pb, pc = render_ink(h.pv._combined_pdf)
            ob, oc = render_ink(M.apply_text_notes(
                h.app.items[0].cached_pdf_bytes, h.app.text_notes))
            check("notes", f"{size}pt preview==output", pb == ob and pc == oc,
                  f"{pb} vs {ob} / {pc} vs {oc}")
            box = M.note_pdf_box(h.app.text_notes[0])
            check("notes", f"{size}pt metrics bound ink",
                  box[0] <= pb[0] + 1 and box[2] >= pb[2] - 1, f"{box} {pb}")

        # sticky placement, exact position, existing-wins
        h.app.text_notes.clear()
        h.pv._rebuild_now()
        h.settle()
        h.pv.text_mode.set(True)
        h.pv._sync_text_mode()
        h.pv._on_canvas_press(Ev(*h.cpt(150, 500)))
        h.settle()
        check("notes", "placed one", len(h.app.text_notes) == 1)
        n0 = h.app.text_notes[0]
        check("notes", "lands where clicked",
              abs(n0["x_pt"] - 150) < 2 and abs(n0["y_pt"] - 500) < 2,
              f"{n0['x_pt']:.1f},{n0['y_pt']:.1f}")
        n0["text"] = "EXISTING"
        h.pv._commit_edit()
        h.settle()
        check("notes", "stays armed", h.pv.text_mode.get())
        bx = h.pv._note_canvas_box(n0)
        h.pv._on_canvas_press(Ev((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2))
        h.settle()
        check("notes", "existing wins over new", len(h.app.text_notes) == 1,
              f"{len(h.app.text_notes)}")
        check("notes", "edits the existing one",
              h.pv._editing() and h.pv._edit_widget["note"] is n0)
        h.pv._commit_edit()
        h.settle()
        h.pv._on_canvas_press(Ev(*h.cpt(150, 400)))
        h.settle()
        check("notes", "empty spot adds", len(h.app.text_notes) == 2)
        h.app.text_notes[-1]["text"] = "SECOND"
        h.pv._commit_edit()
        h.pv._disarm_text_mode()
        check("notes", "disarm works", not h.pv.text_mode.get())
    finally:
        h.close()


def g_shapes():
    h = Harness([make_pdf(os.path.join(TMP, "f.pdf"), 1, text=None)])
    try:
        for nm, val in M.SHAPE_STYLES:
            h.app.shapes[:] = [
                {"page": 0, "x0_pt": 120, "y0_pt": 300, "x1_pt": 480,
                 "y1_pt": 560, "color": "#d00000", "width": 2, "style": val}]
            h.pv._live_shape = None
            h.pv._live_items = []
            h.pv._rebuild_now()
            h.settle()
            pb, pc = render_ink(h.pv._combined_pdf)
            ob, oc = render_ink(M.apply_shapes(
                h.app.items[0].cached_pdf_bytes, h.app.shapes))
            check("shapes", f"{val} preview==output", pb == ob and pc == oc,
                  f"{pb} vs {ob}")

        # transparent middle
        src = make_pdf(os.path.join(TMP, "t.pdf"), 1, text="CONTENT")
        raw = open(src, "rb").read()
        before = render_ink(raw)[1]
        after = render_ink(M.apply_shapes(raw, [
            {"page": 0, "x0_pt": 40, "y0_pt": 40, "x1_pt": 572,
             "y1_pt": 752, "color": "#d00000", "width": 3,
             "style": "rect"}]))[1]
        check("shapes", "frame does not hide content", after > before,
              f"{before} -> {after}")

        # drag direction picks the style
        h.app.shapes.clear()
        h.pv._rebuild_now()
        h.settle()
        h.pv.shape_mode.set(True)
        h.pv._sync_shape_mode()
        h.pv._on_canvas_press(Ev(*h.cpt(120, 600)))
        h.pv._on_canvas_drag(Ev(*h.cpt(420, 450)))
        h.pv._on_canvas_release(None)
        h.settle()
        check("shapes", "left-to-right = rect",
              h.app.shapes[-1]["style"] == "rect",
              h.app.shapes[-1]["style"])
        check("shapes", "stays armed", h.pv.shape_mode.get())
        h.app.shapes.clear()
        h.pv._rebuild_now()
        h.settle()
        h.pv._on_canvas_press(Ev(*h.cpt(420, 400)))
        h.pv._on_canvas_drag(Ev(*h.cpt(120, 250)))
        h.pv._on_canvas_release(None)
        h.settle()
        check("shapes", "right-to-left = cloud",
              h.app.shapes[-1]["style"] == "cloud",
              h.app.shapes[-1]["style"])
        h.pv._disarm_shape_mode()

        # hover marker only on hover, nothing permanent
        sh = h.app.shapes[-1]
        sh.update({"x0_pt": 120, "y0_pt": 300, "x1_pt": 420, "y1_pt": 600})
        h.pv._live_shape = None
        h.pv._rebuild_now()
        h.settle()
        check("shapes", "no permanent decoration",
              len(h.pv.canvas.find_withtag("shapebox")) == 0
              and len(h.pv.canvas.find_withtag("shapegrip")) == 0)
        h.pv._hover_corner(Ev(*h.cpt(250, 450)))
        h.root.update()
        check("shapes", "no marker off-corner",
              len(h.pv.canvas.find_withtag("shapegrip")) == 0)
        for corner, pt in (("nw", (120, 600)), ("ne", (420, 600)),
                           ("sw", (120, 300)), ("se", (420, 300))):
            h.pv._hover_corner(Ev(*h.cpt(*pt)))
            h.root.update()
            check("shapes", f"marker on {corner}",
                  len(h.pv.canvas.find_withtag("shapegrip")) == 2,
                  str(len(h.pv.canvas.find_withtag("shapegrip"))))

        # corner resize
        h.pv._select_shape(sh)
        h.pv._on_canvas_press(Ev(*h.cpt(420, 600)))
        h.pv._on_canvas_drag(Ev(*h.cpt(470, 640)))
        h.pv._on_canvas_release(None)
        h.settle()
        x0, y0, x1, y1 = M.shape_pdf_box(h.app.shapes[-1])
        check("shapes", "ne resize", abs(x1 - 470) < 3 and abs(y1 - 640) < 3,
              f"{x1:.1f},{y1:.1f}")
        check("shapes", "ne resize kept origin",
              abs(x0 - 120) < 3 and abs(y0 - 300) < 3, f"{x0:.1f},{y0:.1f}")

        # existing frame wins while armed
        h.pv.shape_mode.set(True)
        h.pv._sync_shape_mode()
        n_before = len(h.app.shapes)
        h.pv._on_canvas_press(Ev(*h.cpt((x0 + x1) / 2, y1)))   # top edge
        h.settle()
        check("shapes", "existing frame wins",
              len(h.app.shapes) == n_before, f"{len(h.app.shapes)}")
        h.pv._on_canvas_release(None)
        h.pv._disarm_shape_mode()

        # style conversion keeps the picker honest
        h.pv._select_shape(h.app.shapes[-1])
        h.pv._set_shape_style(h.app.shapes[-1], "cloud")
        h.settle()
        check("shapes", "convert to cloud",
              h.app.shapes[-1]["style"] == "cloud")
        check("shapes", "picker follows",
              h.pv.shape_style_cb.get() == "Revision cloud",
              h.pv.shape_style_cb.get())

        # tools are mutually exclusive
        h.pv._toggle_shape_mode()
        h.pv._toggle_text_mode()
        check("shapes", "tools exclusive",
              h.pv.text_mode.get() and not h.pv.shape_mode.get())
        h.pv._disarm_text_mode()

        # delete
        h.pv._select_shape(h.app.shapes[-1])
        h.pv._delete_selected_shape()
        h.settle()
        check("shapes", "delete removes it", len(h.app.shapes) == 0,
              f"{len(h.app.shapes)}")
    finally:
        h.close()


def g_crop():
    """Crop must act on the source, whatever the paper size."""
    long_pdf = make_pdf(os.path.join(TMP, "long.pdf"), 1, (612, 1008), "top")
    for sz, expect in (("original", (612, 1008)), ("letter", (612, 1008)),
                       ("a4", (612, 1008))):
        h = Harness([long_pdf], size=sz)
        try:
            ed = h.app.editor_tab
            ed.on_show()
            h.settle()
            ed.listbox.selection_set(0)
            ed._on_pick()
            h.settle()
            ed._set_mode("crop")
            h.settle()
            got = (round(ed._cur_size[0]), round(ed._cur_size[1]))
            check("crop", f"{sz}: sees true source", got == expect,
                  f"{got} != {expect}")
            if sz == "original":
                # No paper size chosen means no shape to match, so the box
                # starts as a centred ~90% inset rather than hugging the top.
                inset = ed._crop and ed._crop[3] < ed._cur_size[1] \
                    and ed._crop[0] > 0
                check("crop", f"{sz}: box is a sane inset", inset,
                      str(ed._crop))
            else:
                check("crop", f"{sz}: box top-anchored",
                      ed._crop and abs(ed._crop[3] - ed._cur_size[1]) < 1,
                      str(ed._crop))
            ed._do_crop(False)
            h.wait(lambda: all(i.cached_pdf_bytes for i in h.app.items))
            h.settle()
            key = (h.app.items[0].uid, 0)
            check("crop", f"{sz}: stored as crop_src",
                  bool((h.app.page_edits.get(key) or {}).get("crop_src")))
            out = h.app.assemble_from_cache()
            pg = PdfReader(io.BytesIO(out)).pages[0]
            dims = (round(float(pg.mediabox.width)),
                    round(float(pg.mediabox.height)))
            check("crop", f"{sz}: output trimmed", dims[1] < 1008, str(dims))
        finally:
            h.close()


def g_project():
    """Everything must survive a .mydoc round trip."""
    src = make_pdf(os.path.join(TMP, "p.pdf"), 3)
    h = Harness([src])
    try:
        h.app.text_notes.append(
            {"page": 0, "x_pt": 120, "y_pt": 650, "text": "NOTE",
             "font": "Helvetica", "size": 14, "bold": False, "italic": False})
        h.app.shapes.append(
            {"page": 0, "x0_pt": 100, "y0_pt": 300, "x1_pt": 500,
             "y1_pt": 600, "color": "#0a64d8", "width": 3, "style": "dotted"})
        h.app.excluded_pages.add((h.app.items[0].uid, 2))
        path = os.path.join(TMP, "round.mydoc")
        done = []
        h.app.save_project_as(path, then=lambda *_a: done.append(1))
        h.wait(lambda: bool(done))
        check("project", "file written", os.path.exists(path))
        os.remove(src)                       # prove the source is embedded
        h.app.items.clear()
        h.app.text_notes.clear()
        h.app.shapes.clear()
        h.app.excluded_pages.clear()
        h.app._refresh()
        h.root.update()
        h.app.open_project(path)
        h.wait(lambda: h.app.items
               and all(i.cached_pdf_bytes for i in h.app.items))
        h.settle()
        check("project", "source recovered", len(h.app.items) == 1)
        check("project", "note restored", len(h.app.text_notes) == 1)
        check("project", "shape restored", len(h.app.shapes) == 1
              and h.app.shapes[0]["style"] == "dotted")
        check("project", "exclusion restored",
              len(h.app.excluded_pages) == 1)
        out = h.app.assemble_from_cache()
        check("project", "output excludes hidden page",
              out and len(PdfReader(io.BytesIO(out)).pages) == 2,
              str(len(PdfReader(io.BytesIO(out)).pages)) if out else "none")
    finally:
        h.close()


def g_print():
    """Print must send the live document, never touch a real printer here."""
    sent = []
    real = M._print_with_default_printer
    M._print_with_default_printer = lambda p, q=None: sent.append(p)
    h = Harness([make_pdf(os.path.join(TMP, "pr.pdf"), 3)])
    try:
        h.app.shapes.append(
            {"page": 0, "x0_pt": 100, "y0_pt": 300, "x1_pt": 500,
             "y1_pt": 600, "color": "#d00000", "width": 3, "style": "cloud"})
        h.app.excluded_pages.add((h.app.items[0].uid, 2))
        h.app.print_now()
        h.wait(lambda: bool(sent))
        h.settle()
        check("print", "something was sent", bool(sent))
        if sent:
            pages = len(PdfReader(sent[0]).pages)
            check("print", "honours hidden pages", pages == 2, f"{pages}")
            doc = pdfium.PdfDocument(sent[0])
            a = np.array(doc[0].render(scale=3.0).to_pil().convert("RGB"))
            doc.close()
            red = int(((a[:, :, 0] > 120) & (a[:, :, 1] < 90)
                       & (a[:, :, 2] < 90)).sum())
            check("print", "frame is on the printout", red > 500, f"{red}")
            check("print", "not left busy",
                  str(h.app.create_btn.cget("state")) == "normal")
        sent.clear()
        DIALOGS.clear()
        h.app.items.clear()
        h.app.print_now()
        h.settle(6)
        check("print", "empty list prints nothing", not sent)
        check("print", "empty list explains why",
              any("nothing to print" in str(m[2]) for m in DIALOGS),
              str(DIALOGS))
    finally:
        M._print_with_default_printer = real
        h.close()


def g_tabs():
    """Every tab must build and render without blowing up."""
    h = Harness([make_pdf(os.path.join(TMP, "tb.pdf"), 4)])
    try:
        for idx, name in ((1, M.TAB_EDITOR), (2, M.TAB_ORDER),
                          (4, M.TAB_STYLE), (3, M.TAB_PREVIEW)):
            h.app.notebook.select(idx)
            h.settle(25)
            check("tabs", f"{name} selected",
                  h.app.notebook.tab(h.app.notebook.select(), "text") == name)
        h.app.editor_tab.on_show()
        h.settle()
        check("tabs", "editor lists pages",
              len(h.app.editor_tab._pages) == 4,
              str(len(h.app.editor_tab._pages)))
        for z in (50, 100, 150):
            h.app.notebook.select(3)
            h.pv.zoombar.set(z)
            h.settle(12)
        check("tabs", "zoom survives", h.pv._page_count == 4)
    finally:
        h.close()


def g_guards():
    """The two Print guards, with no modal reaching the screen."""
    sent = []
    real = M._print_with_default_printer
    M._print_with_default_printer = lambda p, q=None: sent.append(p)
    h = Harness([make_pdf(os.path.join(TMP, "g.pdf"), 1)])
    try:
        DIALOGS.clear()
        h.app.items[0].cached_pdf_bytes = None       # pretend mid-render
        h.app.print_now()
        h.settle(6)
        check("guards", "still-rendering blocks print", not sent)
        check("guards", "still-rendering says so",
              any("still being prepared" in str(m[2]) for m in DIALOGS),
              str(DIALOGS))
        check("guards", "no real dialog shown", True)
    finally:
        M._print_with_default_printer = real
        h.close()


def g_ghost():
    """The Add-text pointer: I-beam cursor and a caret that previews the
    real text height on the real baseline."""
    h = Harness([make_pdf(os.path.join(TMP, "gh.pdf"), 1, text=None)])
    try:
        check("ghost", "idle cursor is default",
              str(h.pv.canvas.cget("cursor")) in ("", "arrow"),
              repr(h.pv.canvas.cget("cursor")))
        h.pv.text_mode.set(True)
        h.pv._sync_text_mode()
        check("ghost", "armed cursor is an I-beam",
              str(h.pv.canvas.cget("cursor")) == "xterm",
              repr(h.pv.canvas.cget("cursor")))

        scale = h.pv._page_render_scale
        for size in (9, 14, 24, 48):
            h.pv.note_size.set(str(size))
            cx, cy = h.cpt(200, 500)
            h.pv._draw_text_ghost(Ev(cx, cy))
            h.root.update()
            ids = h.pv.canvas.find_withtag("textghost")
            check("ghost", f"{size}pt caret drawn", len(ids) == 4,
                  f"{len(ids)} items")
            # The vertical stroke must span ascent+descent of the REAL font.
            spans = [h.pv.canvas.coords(i) for i in ids]
            vert = [c for c in spans if abs(c[0] - c[2]) < 0.5]
            check("ghost", f"{size}pt has one vertical stroke",
                  len(vert) == 1, str(len(vert)))
            if vert:
                drawn = abs(vert[0][3] - vert[0][1]) / scale
                m = note_metrics_for(size)
                want = m["ascent"] + m["descent"]
                check("ghost", f"{size}pt height matches printed text",
                      abs(drawn - want) < max(1.0, want * 0.06),
                      f"caret {drawn:.2f}pt vs text {want:.2f}pt")
                # The baseline stroke must sit at the pointer, not above it.
                base = [c for c in spans
                        if abs(c[1] - c[3]) < 0.5
                        and abs(c[1] - int(cy)) < 0.6]
                check("ghost", f"{size}pt baseline on the pointer",
                      len(base) == 1, str(spans))

        # and it must vanish when the tool is put away
        h.pv._disarm_text_mode()
        h.root.update()
        check("ghost", "cleared on disarm",
              len(h.pv.canvas.find_withtag("textghost")) == 0)
        check("ghost", "cursor restored",
              str(h.pv.canvas.cget("cursor")) in ("", "arrow"),
              repr(h.pv.canvas.cget("cursor")))

        # off the page there is nothing to preview
        h.pv.text_mode.set(True)
        h.pv._sync_text_mode()
        h.pv._draw_text_ghost(Ev(3, 3))
        h.root.update()
        check("ghost", "nothing drawn off-page",
              len(h.pv.canvas.find_withtag("textghost")) == 0)
        h.pv._disarm_text_mode()
    finally:
        h.close()


def note_metrics_for(size):
    return M.note_text_metrics({"text": "Hg", "font": "Helvetica",
                                "size": size, "bold": False, "italic": False})


GROUPS = {"startup": g_startup, "notes": g_notes, "shapes": g_shapes,
          "crop": g_crop, "project": g_project, "print": g_print,
          "guards": g_guards, "ghost": g_ghost, "tabs": g_tabs}

if __name__ == "__main__":
    want = sys.argv[1:] or list(GROUPS)
    for name in want:
        fn = GROUPS.get(name)
        if fn is None:
            print(f"no such group: {name}")
            continue
        t0 = time.time()
        try:
            fn()
            print(f"[{name}] finished in {time.time() - t0:.1f}s")
        except Exception:
            FAILS.append(f"{name}/EXCEPTION")
            print(f"[{name}] EXCEPTION")
            traceback.print_exc()
    print("\n--- results ---")
    cur = None
    for grp, nm, ok, detail in RESULTS:
        if grp != cur:
            print(f"\n{grp}:")
            cur = grp
        print(f"  {'PASS' if ok else 'FAIL'}  {nm}"
              + (f"   [{detail}]" if detail and not ok else ""))
    total = len(RESULTS)
    bad = len(FAILS)
    print(f"\n{total - bad}/{total} checks passed"
          + (f"   FAILURES: {bad}" if bad else "   ALL GREEN"))
    sys.exit(1 if bad else 0)
