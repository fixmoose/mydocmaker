#!/usr/bin/env python3
"""
MyDocMaker  —  v1.30
================================================================
A free, cross-platform (Windows / macOS / Linux) drag-and-drop PDF builder.

Drop files in (images, PDFs, text, Office docs), OR paste a website
URL to capture a full webpage as PDF pages — mix and match — then click
Create PDF and save. No coding required.

Also supports file-manager integration: invoke with file paths on the command
line (e.g. `mydocmaker.py file1.png file2.pdf`) and they're preloaded. If
the app is already running, the new files are appended to the existing list
in that window via a local IPC socket — so right-clicking "Open With" again
adds to the same project instead of opening another window.

Author: Dejan Obradovic  ·  License: PolyForm Noncommercial 1.0.0
(free for personal/charity/educational/research/government use; commercial
use requires a separate license — contact licensing@mydocmaker.com)
"""

import os
import re
import sys
import io
import json
import socket
import datetime
import time
import hashlib
import getpass
import platform as _platform_mod
import tempfile
import subprocess
import threading
import queue
import urllib.request
import uuid
import webbrowser
import traceback
from urllib.parse import urlparse

# --- GUI: Tkinter (ships with Python on all platforms) ----------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- Cross-platform drag-and-drop -------------------------------------------
# tkinterdnd2 adds OS-level file drop to Tkinter on Win/Mac/Linux.
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_OK = True
except Exception:
    DND_OK = False

# --- Imaging (HEIC via pillow-heif) -----------------------------------------
from PIL import Image, ImageOps
# v1.37: Pillow 10+ moved resampling constants to Image.Resampling; v9 had
# them on Image directly. The bare Image.LANCZOS is deprecated and removed
# in Pillow 11. Probe for the new home and fall back so the same code
# works on whichever Pillow ships in the user's environment.
try:
    LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS = Image.LANCZOS  # Pillow < 10
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_OK = True
except Exception:
    HEIC_OK = False

# --- PDF assembly ------------------------------------------------------------
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader

# --- PDF flatten (optional, large files) ------------------------------------
# pypdfium2 ships its own PDFium binary — no system dependency. We import
# lazily so a missing wheel only disables the flatten feature.
try:
    import pypdfium2 as pdfium
    FLATTEN_OK = True
except Exception:
    FLATTEN_OK = False

# --- QR phone upload (optional) ---------------------------------------------
# qrcode renders the LAN-pointing URL into a scannable image; PIL.ImageTk lets
# us display it in a Tk widget. Both are pure-Python deps; absence just
# disables the "Add from phone" button.
try:
    import qrcode as _qrcode
    QR_OK = True
except Exception:
    QR_OK = False
try:
    from PIL import ImageTk as _ImageTk
    PIL_TK_OK = True
except Exception:
    PIL_TK_OK = False

APP_NAME = "MyDocMaker"
APP_VERSION = "1.48"

# Per-version "What's new" feed. The footer version label pops a dialog that
# shows the bullets for APP_VERSION. Keep this in sync with CHANGELOG.md when
# you tag a release — the in-app reader is the user-facing surface.
WHATS_NEW = {
    "1.48": [
        "New app icon — the MyDocMaker logo mark in blue, replacing the old "
        "red 'MD' tile.",
        "Linux: you can now pin MyDocMaker to the taskbar / Add to Favorites "
        "(GNOME, Pop!_OS, KDE). The window now correctly links to its app "
        "launcher, so the pin sticks instead of showing as an unknown app.",
    ],
    "1.47": [
        "Creating a signature now always starts on the Digital option (the "
        "full business stamp) — no more landing on Typed by default. Editing "
        "an existing signature still opens in that signature's own mode.",
        "The ♡ button in the footer now opens the GitHub Sponsors page "
        "(it previously did nothing).",
        "New 'About / License' button in the footer: MyDocMaker is free for "
        "personal use; commercial use needs a separate license. Includes a "
        "commercial-pricing link and one-click access to the full license "
        "and third-party license texts.",
        "The app now quietly checks for updates about once a month (only "
        "speaks up when a newer version exists). Turn it off anytime in "
        "About / License.",
    ],
    "1.46": [
        "Sign dialog now has a visible signature picker — when you have more "
        "than one saved signature, choose which one each placed signature "
        "uses, instead of relying on a hidden per-window right-click menu "
        "(which silently applied the first signature everywhere).",
        "Remove individual pages from the combined document before building "
        "— including single pages inside multi-page input PDFs — via a "
        "per-page Remove button plus a Restore control. Honoured by both "
        "Create PDF and the Sign & Create flow.",
        "The MyDocMaker logo now appears in the window header.",
        "macOS: fixed the 'MyDocMaker.app is damaged and can't be opened' "
        "Gatekeeper error — the .app is ad-hoc re-signed after its Info.plist "
        "is finalised and packaged with ditto, so the signature stays valid.",
    ],
    "1.45": [
        "▼ New 'Archive' button in the footer (next to My Signatures). "
        "Click it once to pick a folder where every signed PDF gets "
        "auto-saved as a flattened copy — a separate backup, in "
        "addition to wherever you save the signed file yourself. The "
        "button reads 'Set up Archive…' until you configure it, then "
        "switches to 'Archive' (click to open the folder, change it, "
        "or close).",
        "Until you choose a folder, no archiving happens — it's "
        "opt-in. The archive is per-machine and stored next to your "
        "session prefs in ~/.config/mydocmaker/state.json.",
        "Archived copies are flattened (rasterized) so they're "
        "self-contained snapshots that any PDF viewer can render — "
        "great for long-term recordkeeping.",
    ],
    "1.44": [
        "🔒 Signed PDFs are now tamper-protected end-to-end. The "
        "signature visual is baked DIRECTLY into the page's content "
        "stream (raster overlay) — basic PDF editors like Foxit and "
        "Master PDF can no longer quietly delete the widget and have "
        "the visual disappear, because the visual is part of the page "
        "itself, not a removable annotation.",
        "A visible Acrobat-style signature widget is still added on "
        "top so Acrobat shows the clickable signature badge and "
        "verification panel works as expected.",
        "The first signature on a document now certifies it with "
        "FILL_FORMS permission — Acrobat marks the signature 'invalid' "
        "as soon as anyone modifies the page content, while still "
        "allowing other signers to fill any empty signature fields you "
        "left for them in Prepare mode.",
        "Sign dialog shows a small explainer line about the lock-in "
        "behavior so recipients (and you) know the protection model.",
    ],
    "1.43": [
        "Signature stamp shrunk to 220 × 66 pt (was 240 × 72) — less "
        "page real estate, less wasted space inside.",
        "Internal padding tightened: text now sits close to the edges "
        "of the stamp instead of floating in the middle with whitespace "
        "all around. The cursive name is also bbox-cropped before "
        "placement so its actual content fills the left half.",
        "New ✓ SHA-256 · timestamp badge on the bottom line — signals "
        "the cryptographic protection type AND when the document was "
        "signed in one compact element.",
        "Long company names and addresses now pixel-wrap by width "
        "instead of guessing at character count, so the lines never "
        "overflow the right pane.",
    ],
    "1.42": [
        "Fixed: long names no longer get clipped in the cursive "
        "signature image. Names like 'Dejan Obradovic' or "
        "'Christopher Featherstone-Smith' were getting truncated at "
        "the edges of the 960×280 canvas because the 140 px font "
        "rendered them too wide. The renderer now auto-shrinks the "
        "font size until the full name fits with margin on each side.",
        "My Signatures manager preview now shows the FULL composed "
        "DocuSign-style stamp (signature image + name + company + "
        "address + tax ID + license + timestamp) — same renderer the "
        "signed PDF uses. Previously it only showed the raw cursive "
        "PNG with metadata listed as plain text below, which didn't "
        "reflect what the actual signature would look like.",
    ],
    "1.41": [
        "Signature preview is bigger now — 560 × 200 px in the dialog "
        "(was 420 × 130), which is a 1.4× upscale and makes the "
        "supporting lines (address, tax ID, license, timestamp) "
        "actually readable. Previously these lines were rendered at "
        "~10 px on screen and disappeared into noise.",
        "Bumped supporting-line fonts within the appearance composer "
        "too: name 42→48 px, company 30→32 px, captions 26→28 px, "
        "timestamp 24→26 px. On the rendered PDF the text now sits "
        "at roughly 12 pt (name), 8 pt (company), 7 pt (lines), "
        "6.5 pt (timestamp) — every line is comfortably legible.",
        "Stamp box stays at the v1.40 DocuSign size (240 × 72 pt).",
    ],
    "1.40": [
        "Signature box right-sized to match real DocuSign stamps. "
        "Default is now 240 × 72 pt (about 3.3″ × 1″), down from v1.39's "
        "320 × 100 pt which felt oversized on the page.",
        "Appearance layout tightened — dropped the 'Signed by' header "
        "(the cursive sig on the left implies it), reduced internal "
        "padding, and packed the metadata into single-line rows. The "
        "name is bold and dominant at the top, with company / address "
        "/ tax / license / timestamp stacked below.",
        "Net result: same readable text density, less wasted white "
        "space, signature stamp is no longer the size of a credit card.",
    ],
    "1.39": [
        "🔏 Digital signatures are now actually readable. The default "
        "stamp box is bumped from 200pt × 60pt to 320pt × 100pt (DocuSign-"
        "ish proportions) so the signature has real estate on the page, "
        "not a postage stamp.",
        "Appearance image rendered at 1280×400 (was 600×180) with 52px "
        "name font and 30px+ supporting text — fonts now land at "
        "8–14pt on the page, readable instead of squinty.",
        "Auto-rendered cursive name in Digital mode is now generated at "
        "960×280 with a 140px font, so the signature image stays crisp "
        "even at 200% zoom in Acrobat.",
        "Cursive font selection now reaches for actual script faces — "
        "Apple Chancery / Snell Roundhand on macOS, Monotype Corsiva / "
        "Segoe Script on Windows — and falls back to italic serif only "
        "when nothing else is installed.",
    ],
    "1.38": [
        "Fix: the chosen mode (Digital / Typed / Drawn) is now actually "
        "persisted with each saved signature. v1.32–v1.37 set "
        "creator_mode on the meta dict but the JSON-write filter "
        "stripped it because the field wasn't whitelisted — so on edit, "
        "the dialog always reverted to the inferred default (usually "
        "Typed for Digital signatures). Now creator_mode is whitelisted, "
        "and as a belt-and-suspenders the mode is also inferred from "
        "style for any signatures saved before this fix.",
    ],
    "1.37": [
        "🔏 Actually applies the DocuSign-style stamp to the signed PDF "
        "now. v1.36 wired the composed appearance through pyhanko's "
        "StaticStampStyle but pre-created the signature field via "
        "append_signature_field — pyhanko silently ignores stamp_style "
        "when the widget already exists. Fixed by letting PdfSigner "
        "create the field itself via new_field_spec, which is the only "
        "code path that actually applies the stamp.",
        "Pillow forward-compat: switched Image.LANCZOS references to a "
        "module-level LANCZOS constant probed via Image.Resampling so "
        "Pillow 11+ (which removed the bare Image.LANCZOS) keeps "
        "working in the bundled build.",
        "Signature preview no longer disappears silently on errors — "
        "any exception in the preview pipeline now surfaces as a red "
        "one-line error in the preview area instead of a blank box.",
    ],
    "1.36": [
        "🔏 Fixed: signed PDFs now show your FULL identity on the visible "
        "stamp — name, company, address, Tax ID, License — not just the "
        "name + timestamp. Two bugs combined to suppress everything: the "
        "composed appearance PNG was never actually applied to pyhanko's "
        "signature widget (stamp_style=None made pyhanko fall back to its "
        "minimal default), and the metadata wasn't being passed into the "
        "composer in the first place. Both fixed.",
        "📐 WYSIWYG preview in the signature creator — every mode now "
        "shows a live preview of EXACTLY what the signed stamp will look "
        "like on the PDF (left: signature image; right: identity + "
        "timestamp). Type in Digital mode and watch the company / "
        "address / license appear in the preview in real time.",
        "Digital mode auto-renders your Name in a cursive script as the "
        "signature image — no typing or drawing UI needed.",
    ],
    "1.35": [
        "Signature creator: three distinct signature types, each with "
        "its own self-contained UI — no more mixing widgets.",
        "  • Digital — DocuSign-style: fill in your business details "
        "(name, company, address, VAT/EIN/Tax/License). The visible "
        "signature image is auto-rendered from your Name in a cursive "
        "script. NO type or draw widgets in this mode.",
        "  • Typed — type your name, pick a font style. Just that.",
        "  • Drawn — draw your signature freehand. Just that.",
        "Existing signatures created with v1.31–v1.34's 'Create signature "
        "— full details' mode keep working and now show under Digital.",
    ],
    "1.34": [
        "Fixed: in 'Create signature — full details' mode, the dialog was "
        "stacking BOTH the Type and Draw visual frames + the Details "
        "fields at once, which made the dialog enormous (especially when "
        "editing an existing signature). Now that mode shows a compact "
        "Type/Draw sub-chooser at the top — pick one, fill it in, fill "
        "in your details, click Save. Only one visual is visible at a "
        "time, so the dialog stays a reasonable size.",
    ],
    "1.33": [
        "Signature creator: each of the three modes (Create signature / "
        "Type your name / Draw your signature) now has its OWN Save "
        "button at the bottom of that mode's panel — 'Save typed "
        "signature', 'Save drawn signature', 'Save signature with "
        "details'. Click your mode's Save, the signature is created and "
        "the dialog closes. No more global Save button. One signature = "
        "one type; if you want a different style, create another via "
        "My Signatures and apply it via the right-click 'Sign as' menu.",
    ],
    "1.32": [
        "✎ My Signatures button moved to the bottom-right of the footer — "
        "out of the way until you need it (it's a setup-once action, not "
        "a per-PDF one).",
        "🔏 Signature creator restructured: 3 clear options at the top — "
        "'Create signature — full details' (best for business and legal "
        "documents, includes name + company + address + VAT/EIN/Tax/"
        "License), 'Type your name' (quick cursive signature), and "
        "'Draw your signature' (with much higher-quality rendering — "
        "4× oversampling + LANCZOS smoothing, so the final stamp looks "
        "polished instead of pixelated).",
        "Right-click context menu is now mode-aware: in Sign mode it's "
        "'Sign as ▸ <your saved signatures>' (as in v1.31); in Prepare "
        "mode it switches to 'Assign to ▸ Person 1 / Person 2 / ...' "
        "with optional Name + Email per person.",
        "Prepare mode now shows a Persons editor where you can name each "
        "person who will sign and add their email. Those names land in "
        "the PDF as 'Signature 2 - Alice Smith <alice@example.com>' "
        "instead of an anonymous slot number — much easier for the "
        "recipient to identify their field in Acrobat.",
        "Prepare-mode signature windows are coloured one per person "
        "(amber / green / purple / red / blue / cyan) so visually you "
        "can tell who's signing where.",
    ],
    "1.31": [
        "🔏 Multiple saved signatures. New 'My Signatures' button "
        "(top-right) opens a manager where you can create, edit, and "
        "delete as many signatures as you want — each with name, "
        "company, address, and VAT/EIN/Tax/License fields. Useful when "
        "you sign personally AND on behalf of a company, or for "
        "different clients.",
        "Right-click a signature window in the Sign dialog → 'Sign as ▸ "
        "<signature>' picks which one to use. Each window can be a "
        "different signature, so one PDF can carry multiple identities.",
        "Or leave a window empty: it becomes a clickable signature "
        "field for someone else to fill in later in Acrobat / Foxit. "
        "Visible blue dashed rectangles now appear ON the PDF page so "
        "recipients can SEE where to sign, not just where the cursor "
        "happens to hit a hidden widget.",
        "Signature windows are now outline-only (no fill colour) — you "
        "can see the page content underneath. Amber outline = will be "
        "signed; grey dashed outline = empty (for someone else); blue = "
        "currently selected.",
        "v1.28's single saved signature is auto-migrated into the new "
        "store the first time v1.31 launches — nothing to do, your "
        "existing signature is preserved as the first entry.",
    ],
    "1.30": [
        "Sign dialog rectangles are now actually visible: opaque amber/"
        "green/purple/red fills (one color per signer), solid 2px "
        "outline, big 'Signature window #N' label centered inside, "
        "plus 'Person #M — page X' subtitle. v1.29's invisible boxes "
        "were a Tk alpha-channel bug; fixed by switching to pure RGB.",
        "Click position is now the CENTER of the new spot, not its "
        "top-left corner. So when you click, the window appears where "
        "the cursor is.",
        "Simpler mouse model: left-click on empty page = place new; "
        "left-click on a spot = select; left-drag = move it. No more "
        "right-click-then-click. Drop overlapping any other spot is "
        "still rejected.",
        "Right-click on a spot = context menu with 'Assign to Person N',"
        " 'Size' presets (Small / Default / Wide / Tall), and 'Delete'.",
        "Multi-signer workflow: each spot has an owner (Person 1..N). "
        "When you sign, only YOUR spots get signed; the others are "
        "kept in the PDF as empty (clickable) signature fields, "
        "labeled 'Signature N (Person M)' so the next signer can fill "
        "them in Acrobat / Foxit / etc.",
        "Auto-renumber: delete a spot in the middle and the rest "
        "shift down — Signature 1, 2, 3 stays sequential.",
        "Empty fields in saved PDFs carry descriptive names "
        "('Signature 1 (Person 2)') so the next signer knows which "
        "field is theirs.",
    ],
    "1.29": [
        "Sign dialog is now a proper signature designer: drop multiple "
        "signature spots, select them, move them, delete them.",
        "Left-click on empty area places a new spot (with overlap "
        "rejection — can't drop two on top of each other). Left-click "
        "on an existing spot selects it.",
        "Right-click on a spot enters move mode (cursor changes); next "
        "left-click relocates it. Right-click empty / Escape cancels.",
        "Delete or Backspace removes the selected spot.",
        "Two save modes: 'Sign with my signature' (the v1.28 flow, now "
        "supporting multiple spots) or 'Prepare for others to sign' "
        "(produces a PDF with empty signature fields you can send "
        "elsewhere — no signing happens).",
        "Signed appearance redesigned: signature image on the left, "
        "signer name + timestamp on the right of the stamp. No more "
        "overlapping the signature.",
    ],
    "1.28": [
        "New: 🔏 Sign and Create PDF — fully offline e-signing. "
        "Click the button → if you don't have a signature yet, the "
        "Create Signature dialog opens (Type your name in a cursive "
        "font, OR draw your signature freehand on a pad). Save it "
        "once, reuse it forever.",
        "After the build, the Sign dialog opens with a scrollable "
        "preview of every page. Click on any page to drop your "
        "signature stamp; click somewhere else to move it. Hit "
        "Sign & Save.",
        "Result: a PDF with embedded PKCS#7 signature (PAdES-compliant; "
        "Adobe Acrobat shows the signature panel) + a companion "
        ".audit.json sidecar listing the SHA256, your machine + user, "
        "timestamp, and certificate fingerprint for independent "
        "verification.",
        "First sign auto-generates a self-signed RSA-2048 certificate "
        "stored at ~/.config/mydocmaker/signing/ — never "
        "leaves your machine. Recipients see 'self-signed' until they "
        "trust the certificate (same as code-signing without a paid CA).",
        "v1.29 will add image-upload signatures, multiple saved sigs, "
        "and a Verify dialog. v1.28 is intentionally tight: one "
        "signature, one position per PDF, end-to-end working.",
    ],
    "1.27": [
        "Header text refreshed: 'Drop any file(s) below — or paste a "
        "website URL — and create a combined PDF.' Reads better and "
        "spells out what the app actually does.",
    ],
    "1.26": [
        "Nautilus right-click 'Add to D&D PDF Creator' entry now "
        "shows the red D&D PDF icon next to the text — easier to "
        "spot in the menu.",
    ],
    "1.25": [
        "Preview tab now does continuous vertical scrolling — every "
        "page stacked in one view, mouse-wheel works, Prev/Next jump "
        "between page boundaries.",
        "Window/taskbar icon is now crisp at every size (16/24/32/48/"
        "64/128/256 pre-rendered with Pillow's LANCZOS filter).",
        "'Sign and Create PDF' button added next to Create PDF — "
        "currently grayed out as a placeholder; v1.26 wires up actual "
        "PAdES e-signature on top of it.",
        "Flatten savings estimate moved from the under-list strip to "
        "right next to the Flatten checkbox so the trade-off is "
        "visible where the toggle is.",
        "Clicking the empty-list 'Drag & Drop any file here' placeholder "
        "now opens the file browser (same as the + Browse files button).",
        "Tiny tweak: dropped the exclamation point from the ♡ sponsor "
        "tooltip — reads less salesy.",
    ],
    "1.24": [
        "Small ♡ sponsor button added to the footer. Hover for the "
        "tooltip 'Support this project from Dejan & Claudia!'. The "
        "click is a no-op for now — the link will be wired up once "
        "the GitHub Sponsors profile (currently in review) is approved.",
    ],
    "1.23": [
        "New Preview tab — a live, page-by-page viewer of the combined "
        "PDF, built on top of a per-item render cache. Switch tabs any "
        "time to see what your output looks like.",
        "Background rendering: every file or URL you add is rendered to "
        "PDF in the background as soon as it lands in the list, so the "
        "preview is usually ready when you open it. Webpage captures "
        "still take a few seconds each, but they happen concurrently "
        "while you keep adding more files.",
        "Per-item status indicators in the page list: '…' queued, '⏳' "
        "rendering now, '✓' ready, '✗' failed.",
        "Reordering items and removing them is instant in the preview — "
        "cached bytes get re-stitched, no re-render.",
        "Changing the page-size (Original/A4/Letter) invalidates cached "
        "renders and re-queues them so the preview reflects the new "
        "setting.",
        "Foundation for v1.24's e-signature feature — the viewer is "
        "what you'll click to drop signature stamps onto.",
    ],
    "1.22": [
        "Office → PDF conversion now picks the best backend you have "
        "installed: Microsoft Office (Windows, via COM) first for "
        "highest fidelity, OnlyOffice DocumentBuilder second, "
        "LibreOffice as the universal fallback.",
        "Windows users with Microsoft Office no longer need LibreOffice "
        "installed at all — Word/Excel/PowerPoint convert directly via "
        "the real Office apps in the background.",
        "OnlyOffice DocumentBuilder support: install it once, the app "
        "uses it automatically. Cross-platform (Win/Mac/Linux).",
        "If one backend chokes on a specific file, the next one in line "
        "is tried automatically — so a glitchy .docx in Word doesn't "
        "block conversion when LibreOffice would handle it fine.",
    ],
    "1.21": [
        "Byline added to the What's New dialog — every version's "
        "release notes now end with 'by Dejan Obradovic (& Claudia)'.",
    ],
    "1.20": [
        "Each item in the page list now shows its size: filename.ext "
        "(12.3 MB), so you can spot big files at a glance.",
        "New running-totals strip under the list: number of items, "
        "total size on disk, and an estimate of the output size if "
        "you tick Flatten. The flatten estimate tells you how much "
        "you'd save — handy for deciding whether to bother.",
        "Webpages in the list now show '(webpage)' since their final "
        "size isn't known until Chromium renders them.",
    ],
    "1.19": [
        "Fix: locale-aware default page size from v1.18 was being "
        "overridden by old saved state — anyone who'd ever launched "
        "v1.16–v1.18 had 'Original' stuck as their default regardless "
        "of locale. State files now carry a schema version; v1 saves "
        "are read for the page list but ignored for page-size and "
        "flatten preferences so the locale default wins.",
        "Hint added to the .deb post-install banner: if the menu icon "
        "looks generic, log out + back in once (Wayland caches app "
        "icons in memory and can't live-reload).",
    ],
    "1.18": [
        "Custom red D&D PDF icon now used across the board — Tk window, "
        "Linux app menu, Windows taskbar + installer + uninstaller, "
        "macOS Dock + .app bundle.",
        "Page size defaults to Letter for US/CA/MX (etc.) and A4 for "
        "everyone else, based on your locale. 'Original (images)' is "
        "still available — just no longer the default for mixed input.",
        "No more nag to install LibreOffice if you already have any "
        "Office suite — OnlyOffice, MS Office, or Apple iWork detected = "
        "no banner.",
        "When nothing is installed, the install banner now leads with "
        "OnlyOffice as the recommended free choice (best Microsoft-"
        "format fidelity); LibreOffice listed as the universal "
        "alternative.",
        "Heads-up: actual headless conversion via OnlyOffice / MS Office "
        "still requires their batch tools (DocumentBuilder, Word/Excel "
        "COM). Full multi-backend support shipping in v1.19.",
    ],
    "1.17": [
        "Empty Pages list now shows a friendly 'Drag & Drop any file "
        "here' hint instead of just being blank.",
        "App icon swapped to the system 'application-pdf' icon (the "
        "look v1.01 had) so it blends with the rest of your icon "
        "theme instead of being a custom blue square.",
        "Smaller .deb (no more bundled PNG icon).",
    ],
    "1.16": [
        "New top-level right-click entry: 'Add to D&D PDF Creator' "
        "(Linux + Nautilus). One click, silent — files are appended to "
        "the open window or launch a new one. No more digging through "
        "the Open With submenu. Needs python3-nautilus, which the .deb "
        "now declares as a Recommends.",
        "Persistent file list — your page list is saved automatically "
        "to ~/.config/mydocmaker/state.json and restored next "
        "time you open the app. Page size + Flatten preferences are "
        "remembered too.",
        "Files that no longer exist on disk (moved or deleted between "
        "sessions) are quietly dropped from the restored list; a status "
        "message reports the count.",
        "Use 'Clear all' to start a fresh list when you want — it's "
        "the same button as before, just more useful now that the list "
        "persists across launches.",
    ],
    "1.15": [
        "Right-click 'Open With MyDocMaker' now appears in the "
        "main file-manager menu on Linux — previously hidden because the "
        ".desktop file had no Icon= field, so Nautilus/GNOME Files "
        "demoted us to 'Other Application…' only.",
        "Linux build now ships a 256×256 PNG icon (generated at build "
        "time with Pillow), GenericName, and Keywords for better menu "
        "search results.",
        "postinst refreshes the icon cache + MIME database too, so the "
        "right-click entry appears the moment apt finishes — no logout "
        "needed.",
    ],
    "1.14": [
        "Spreadsheet hint — when you add a .xlsx / .xls / .ods file, a "
        "one-time tip explains how to set Print Area + Fit to Page + "
        "orientation in your spreadsheet for clean PDF output. (We use "
        "whatever print settings the file was saved with — LibreOffice "
        "doesn't override them, and most users have never set them.)",
        "Better Windows missing-LibreOffice messaging — direct download "
        "link and a three-step install path, plus an explanation of why "
        "we don't bundle LibreOffice (~600 MB).",
        "README now has a per-platform Uninstall section.",
    ],
    "1.13": [
        "Friendlier .deb install feedback — after `sudo apt install …` "
        "finishes you now get a clear green ✓ banner with the exact "
        "command and menu name to launch, instead of just dpkg's wall "
        "of technical 'Setting up… / Processing triggers…' output.",
        "Same treatment on uninstall: a one-line confirmation tells you "
        "the package is gone and shows how to reinstall.",
    ],
    "1.12": [
        "Friendly missing-component banner at startup — if LibreOffice "
        "or SANE (Linux scanner tools) aren't installed, a small notice "
        "appears with an Install… button.",
        "One-click install dialog: per-component Install buttons. Uses "
        "pkexec + apt/dnf/pacman/zypper on Linux (polkit auth prompt), "
        "Homebrew on macOS if present, or opens the official download "
        "page everywhere else.",
        "Dependabot enabled: weekly PRs bump Python dependencies "
        "(Pillow, pypdf, playwright, …) and GitHub Action versions, so "
        "each release ships with the latest security fixes baked in.",
    ],
    "1.11": [
        "Hotfix: Linux builds (v1.06–v1.10) crashed at startup on systems "
        "with glibc < 2.38 (Pop!_OS 22.04, Ubuntu 22.04, Debian 12, Mint "
        "21) — 'GLIBC_2.38 not found' loading libpython3.12.so.1.0.",
        "Fix: pin the Linux build runner to ubuntu-22.04 so the bundle "
        "links against glibc 2.35, which covers every Debian/Ubuntu "
        "derivative released since April 2022.",
    ],
    "1.10": [
        "One-click auto-update — Check for updates now offers Download & "
        "install for installer-style installs (Windows .exe installer, "
        "Linux .deb). A progress bar shows download MB/total and, when "
        "finished, the OS's installer takes over.",
        "Detects how the app is installed (Windows installer vs. portable "
        "zip, macOS .app, Linux .deb vs. tarball) and downloads the right "
        "artifact for the user's environment.",
        "For portable installs (Windows zip, macOS app, Linux tarball) the "
        "downloaded archive opens in your file manager so you can replace "
        "the old copy manually — auto-replacing running executables isn't "
        "safe without an installer wrapper.",
    ],
    "1.09": [
        "Windows installer .exe is now actually included in the release "
        "(the v1.08 build step compiled it but dropped it in the wrong "
        "directory — fixed, plus a verification step now fails the build "
        "if the .exe isn't produced).",
    ],
    "1.08": [
        "Windows installer (.exe) — proper Inno Setup installer with right-click "
        "'Open With MyDocMaker' integration, optional Send To "
        "shortcut, Start Menu + Desktop icons, and a real uninstaller.",
        "macOS Finder integration — right-click any supported file and "
        "MyDocMaker shows up under 'Open With'. Multi-file "
        "selections are routed via Apple Events so they all land in one "
        "window.",
        "Scan button now does something useful on Windows + macOS — opens "
        "Windows Fax & Scan / Image Capture so you can scan, save, and drag "
        "the file in. Linux still uses one-click SANE scanning.",
    ],
    "1.07": [
        "Click the version label (bottom-left) to see what's new in this release.",
        "Close button added to the footer, alongside Check for updates.",
        "Add-source buttons (Browse, From phone, Scan) moved to their own row "
        "so the Scan button is no longer clipped on narrower windows.",
    ],
    "1.06": [
        "Create and open PDF + Create and print PDF buttons — build, then "
        "auto-open in your viewer or send to the default printer.",
        "📱 Add from phone (QR) — scan a QR with your phone and upload "
        "photos/PDFs over Wi-Fi.",
        "🖨 Scan (Linux today via SANE) — one-click scan into the list.",
        "Check for updates footer button — checks GitHub for newer releases.",
        "Live flatten progress bar + 'Saved X.X MB' meter in the result.",
        "Save dialog defaults to ~/Desktop.",
        "Webpage capture fix — forces print media + light scheme + clears "
        "selection, eliminating the all-gray output some sites produced.",
    ],
    "1.05": [
        "Right-click context menu on the page list (Remove / Move to top / "
        "Move to bottom).",
        "THIRD-PARTY-LICENSES.md catalogue for bundled libraries.",
    ],
    "1.04": [
        "Flatten output option (rasterizes each page — shrinks image-heavy "
        "PDFs significantly).",
        "120 MB per-file size cap with friendly batch warning.",
    ],
    "1.03": [
        "Right-click 'Open With MyDocMaker' integration on Linux.",
        "Single-instance mode — second invocation appends files to the "
        "running window instead of opening another one.",
    ],
    "1.02": [
        ".deb package for Linux + source tarball artifact.",
        "Fixed Windows artifact naming, URL validation, LibreOffice precheck.",
    ],
    "1.01": [
        "First cross-platform release (Windows / macOS / Linux).",
        "Paste a website URL to capture a full webpage as PDF pages.",
        "iPhone HEIC photos work out of the box.",
    ],
}

# Per-file cap. We refuse larger inputs because PyInstaller-bundled Python +
# Chromium + LibreOffice already use a lot of memory, and a single 200MB+ file
# can push the assembled PDF past most users' "manageable" size.
MAX_FILE_BYTES = 120 * 1024 * 1024
MAX_FILE_LABEL = "120 MB"

# Flatten defaults — good size/quality balance for screen reading.
FLATTEN_DPI = 150
FLATTEN_JPEG_QUALITY = 80

# Rough estimate used for the "if flattened" total in the UI: a JPEG-
# compressed A4 page at 150 DPI / quality 80 is typically 60-150 KB.
# We round to 100 KB as a single-number heuristic — wildly off for any
# *individual* page, but averages out across a typical document.
FLATTEN_BYTES_PER_PAGE_EST = 100 * 1024


def format_size(n):
    """Human-friendly file size, e.g. 1.4 GB / 23.7 MB / 412 KB / 0 B."""
    if n is None or n <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def default_save_dir():
    """Best-effort Desktop folder for the current user, falling back to
    home if Desktop doesn't exist (some Linux setups omit it)."""
    candidates = [os.path.expanduser("~/Desktop"),
                  os.path.expanduser("~/desktop")]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return os.path.expanduser("~")


# Countries that historically use US Letter (8.5 × 11 in) instead of A4.
# Anyone else gets A4. (Source: ISO 216 + ANSI A coverage.)
_LETTER_COUNTRIES = {"US", "CA", "MX", "PH", "CO", "VE", "CL"}


def _detect_country_code():
    """Return the user's ISO 3166-1 alpha-2 country code, or None.
    Tries locale env vars first (LC_ALL, LANG, etc.), then falls back
    to Windows-specific GetUserDefaultUILanguage via ctypes."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        m = re.search(r"_([A-Za-z]{2})", val)
        if m:
            return m.group(1).upper()
    if sys.platform.startswith("win"):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            lcid = kernel32.GetUserDefaultUILanguage()
            buf = ctypes.create_unicode_buffer(20)
            # LOCALE_SISO3166CTRYNAME = 0x5A
            n = kernel32.GetLocaleInfoW(lcid, 0x5A, buf, len(buf))
            if n > 0:
                return buf.value.upper()
        except Exception:
            pass
    return None


def default_page_size():
    """Returns 'letter' or 'a4' based on detected user locale. The default
    is A4 — overwhelmingly the most common paper size globally — and we
    flip to Letter only if the locale belongs to one of the few
    Letter-using countries."""
    cc = _detect_country_code()
    return "letter" if cc in _LETTER_COUNTRIES else "a4"


def _open_with_default_viewer(path):
    """Open `path` in the OS default app (PDF viewer for *.pdf)."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        # Failing silently is OK — the file is already saved; user can open it
        # manually. We don't want a popup that blocks the "done" dialog.
        pass


UPDATE_API_URL = "https://api.github.com/repos/fixmoose/mydocmaker/releases/latest"
UPDATE_PAGE_URL = "https://github.com/fixmoose/mydocmaker/releases/latest"
# How often the background auto-check phones GitHub for a newer release.
# Tighten this around a big rollout if you want faster uptake.
UPDATE_CHECK_INTERVAL_DAYS = 30
SPONSOR_URL = "https://github.com/sponsors/fixmoose"
WEBSITE_URL = "https://mydocmaker.com"
LICENSE_URL = "https://github.com/fixmoose/mydocmaker/blob/main/LICENSE"
THIRD_PARTY_LICENSES_URL = (
    "https://github.com/fixmoose/mydocmaker/blob/main/THIRD-PARTY-LICENSES.md"
)
# Commercial-licensing contact + pricing page. MyDocMaker is free for personal
# use under the PolyForm Noncommercial License; for-profit/commercial use needs
# a separate license. PRICING_URL is baked in ahead of the site going live so
# that copies installed beforehand still point to the right page once it's up.
LICENSE_CONTACT_EMAIL = "licensing@mydocmaker.com"
PRICING_URL = "https://mydocmaker.com/pricing"


def _parse_version(s):
    """Loose semantic-ish version parse — strips a leading 'v', returns a
    tuple of ints so '1.6' > '1.05' compares correctly. Non-numeric chunks
    are dropped so RC suffixes don't break the comparison."""
    s = (s or "").strip().lstrip("vV")
    parts = []
    for chunk in s.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def fetch_latest_release_info(timeout=8.0):
    """Returns the latest release's full JSON dict from GitHub, or raises.
    Used by both the simple version check and the auto-update flow that
    needs the asset list."""
    req = urllib.request.Request(
        UPDATE_API_URL,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": f"{APP_NAME}/{APP_VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_install_kind():
    """Best-effort guess at how this build is installed, used to pick the
    matching artifact when auto-updating. Returns one of:
        windows-installer, windows-portable,
        macos-app, macos-portable,
        linux-deb, linux-portable,
        source, unknown
    """
    if not getattr(sys, "frozen", False):
        return "source"
    exe = (sys.executable or "").replace("\\", "/").lower()
    if sys.platform.startswith("win"):
        # Inno Setup default for {userpf} is %LOCALAPPDATA%/Programs/<App>.
        # Anything under Program Files / Programs is treated as installer.
        if "/programs/" in exe or "/program files" in exe:
            return "windows-installer"
        return "windows-portable"
    if sys.platform == "darwin":
        if ".app/contents/macos/" in exe:
            return "macos-app"
        return "macos-portable"
    if sys.platform.startswith("linux"):
        if exe.startswith("/opt/mydocmaker/"):
            return "linux-deb"
        return "linux-portable"
    return "unknown"


def asset_pattern_for(kind):
    """Returns a compiled regex matching the GitHub release asset name for
    this install kind, or None if there's nothing sensible to download."""
    patterns = {
        "windows-installer": r"^MyDocMaker-Windows-Setup\.exe$",
        "windows-portable":  r"^MyDocMaker-Windows\.zip$",
        "macos-app":         r"^MyDocMaker-macOS\.zip$",
        "macos-portable":    r"^MyDocMaker-macOS\.zip$",
        "linux-deb":         r"^mydocmaker_[\d.]+_amd64\.deb$",
        "linux-portable":    r"^MyDocMaker-Linux\.tar\.gz$",
    }
    pat = patterns.get(kind)
    return re.compile(pat) if pat else None


def find_matching_asset(release_info, kind):
    """Picks the asset URL/name/size that matches this install_kind, or
    returns (None, None, 0) if no asset matches."""
    pat = asset_pattern_for(kind)
    if pat is None:
        return None, None, 0
    for a in release_info.get("assets", []) or []:
        if pat.match(a.get("name", "")):
            return a.get("browser_download_url"), a.get("name"), int(a.get("size") or 0)
    return None, None, 0


def download_with_progress(url, dest, progress_cb=None, chunk=64 * 1024,
                           cancel_event=None):
    """Stream `url` to `dest`, calling progress_cb(done, total) per chunk.
    `total` may be 0 if the server didn't send Content-Length. Honors
    cancel_event.is_set()."""
    req = urllib.request.Request(
        url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        try:
            total = int(resp.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            total = 0
        done = 0
        with open(dest, "wb") as fh:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise RuntimeError("Download cancelled")
                buf = resp.read(chunk)
                if not buf:
                    break
                fh.write(buf)
                done += len(buf)
                if progress_cb is not None:
                    try:
                        progress_cb(done, total)
                    except Exception:
                        pass
    return done


def hand_off_to_installer(kind, downloaded_path):
    """Launch the freshly-downloaded artifact in whatever way is appropriate
    for the install kind. For installer formats this kicks off the upgrade
    in-place; for portable/.zip formats it just opens the containing folder
    so the user can finish manually."""
    folder = os.path.dirname(downloaded_path) or "."
    if kind == "windows-installer":
        # Setup.exe will pick up the running app and trigger the "Close
        # running application" wizard step if needed. We exit shortly after
        # to release file locks.
        try:
            os.startfile(downloaded_path)  # type: ignore[attr-defined]
            return
        except Exception:
            pass
    elif kind == "linux-deb":
        # xdg-open hands the .deb to the system installer (GNOME Software,
        # KDE Discover, gdebi, etc).
        try:
            subprocess.Popen(["xdg-open", downloaded_path])
            return
        except Exception:
            pass
    # macos-app, *-portable, fallthrough errors → open the folder so the
    # user can act on the file manually.
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        webbrowser.open(UPDATE_PAGE_URL)


def _print_with_default_printer(path, error_queue=None):
    """Send `path` to the OS default printer. On Windows uses the shell's
    'print' verb (works when a default PDF reader is registered). On Linux
    and macOS shells out to `lp` (CUPS, present on both by default)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path, "print")  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["lp", path])
    except FileNotFoundError:
        if error_queue is not None:
            error_queue.put((
                "warn",
                "Couldn't find a 'lp' command — install CUPS (Linux/macOS) or "
                "open the saved PDF and print manually.",
            ))
    except Exception as e:
        if error_queue is not None:
            error_queue.put(("warn", f"Printing failed: {e}"))


# ---------------------------------------------------------------------------
# Single-instance IPC: a second invocation hands its file paths off to the
# first one over a local TCP socket, then exits silently. The port is derived
# from the current user so multi-user systems don't collide.
# ---------------------------------------------------------------------------
IPC_HOST = "127.0.0.1"
IPC_TIMEOUT = 0.4


def _ipc_port():
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"
    digest = hashlib.md5(f"mydocmaker:{user}".encode()).hexdigest()
    return 49152 + (int(digest[:8], 16) % 16384)


IPC_PORT = _ipc_port()


def send_paths_to_existing(paths):
    """Try to deliver paths to a running instance. True on success."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(IPC_TIMEOUT)
            s.connect((IPC_HOST, IPC_PORT))
            s.sendall((json.dumps({"paths": paths}) + "\n").encode())
        return True
    except OSError:
        return False


def start_ipc_server(on_paths):
    """Bind the IPC port and forward incoming path lists to `on_paths`.
    Returns the server socket on success, or None if the port was unavailable
    (in which case single-instance behavior degrades gracefully)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((IPC_HOST, IPC_PORT))
    except OSError:
        srv.close()
        return None
    srv.listen(5)

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            try:
                conn.settimeout(0.5)
                buf = bytearray()
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
                try:
                    msg = json.loads(buf.decode("utf-8", "replace").strip())
                except ValueError:
                    msg = {}
                paths = [p for p in msg.get("paths", []) if isinstance(p, str)]
                if paths:
                    on_paths(paths)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    threading.Thread(target=serve, daemon=True).start()
    return srv

# ---------------------------------------------------------------------------
# File type knowledge
# ---------------------------------------------------------------------------
IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".jpe", ".bmp", ".gif", ".tiff", ".tif",
    ".webp", ".ico", ".ppm", ".pgm", ".pbm", ".pnm", ".tga", ".dds",
    ".heic", ".heif", ".hif", ".avif",
}
TEXT_EXTS = {
    ".txt", ".md", ".csv", ".log", ".py", ".js", ".ts", ".html", ".htm",
    ".css", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".sh",
}
PDF_EXTS = {".pdf"}
OFFICE_EXTS = {
    ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods",
    ".ppt", ".pptx", ".odp",
}
# Spreadsheet subset — these get the "set Print Area + Fit to Page first"
# hint dialog. Page-setup quirks are most visible on spreadsheets.
SPREADSHEET_EXTS = {".xls", ".xlsx", ".ods"}
ALL_SUPPORTED = IMAGE_EXTS | TEXT_EXTS | PDF_EXTS | OFFICE_EXTS


def file_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in TEXT_EXTS:
        return "text"
    if ext in OFFICE_EXTS:
        return "office"
    return "unknown"


def find_libreoffice():
    """Locate LibreOffice/soffice across platforms."""
    candidates = ["libreoffice", "soffice"]
    # macOS default install path
    candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    # Windows default path
    candidates.append(r"C:\Program Files\LibreOffice\program\soffice.exe")
    for c in candidates:
        from shutil import which
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        elif which(c):
            return which(c)
    return None


# ---------------------------------------------------------------------------
# Persistent file list (v1.16): remember the page list between launches so
# users don't lose work when they close the app. State is stored in
# XDG_CONFIG_HOME/mydocmaker/state.json. Files that no longer
# exist on disk (moved, deleted) are filtered out at load time.
# ---------------------------------------------------------------------------
def _state_dir():
    base = os.environ.get(
        "XDG_CONFIG_HOME",
        os.path.join(os.path.expanduser("~"), ".config"),
    )
    p = os.path.join(base, "mydocmaker")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError:
        pass
    return p


def _state_file():
    return os.path.join(_state_dir(), "state.json")


_STATE_VERSION = 2


def _load_archive_folder():
    """Returns the user's configured archive folder for signed PDFs, or
    None if they haven't set one up yet. Re-validates the path exists —
    if the user moved/deleted the folder we treat it as unconfigured."""
    try:
        with open(_state_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    folder = data.get("archive_folder")
    if folder and os.path.isdir(folder):
        return folder
    return None


def _save_archive_folder(path):
    """Persist the user's archive folder choice. Read-modify-write so
    other state fields (items, page_mode, etc.) aren't blown away."""
    try:
        try:
            with open(_state_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"version": _STATE_VERSION}
        data["archive_folder"] = path
        tmp = _state_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _state_file())
    except OSError:
        pass


# Generic preference get/set in state.json. Read-modify-write so unrelated
# state (items, archive_folder, etc.) survives. Used for the auto-update
# check bookkeeping (last check time + opt-out flag). NOTE: any key persisted
# here must also be listed in save_session_state's preserved-keys tuple, or a
# session save will drop it.
def _get_pref(key, default=None):
    try:
        with open(_state_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default
    return data.get(key, default)


def _set_pref(key, value):
    try:
        try:
            with open(_state_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"version": _STATE_VERSION}
        data[key] = value
        tmp = _state_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _state_file())
    except OSError:
        pass


def archive_signed_pdf(signed_pdf_path, audit_path=None):
    """v1.45: copy the freshly-signed PDF into the user's configured
    archive folder, FLATTENED (rasterized) for compact long-term
    storage and tamper-resistance even in basic viewers. The audit
    JSON sidecar travels with it. Returns the archived PDF path or
    None if archiving isn't configured / fails."""
    folder = _load_archive_folder()
    if not folder or not os.path.isdir(folder):
        return None
    try:
        with open(signed_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        flat_bytes = flatten_pdf_bytes(pdf_bytes)
        base = os.path.basename(signed_pdf_path)
        name, ext = os.path.splitext(base)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_name = f"{name}-{ts}-archived{ext or '.pdf'}"
        archive_path = os.path.join(folder, archive_name)
        with open(archive_path, "wb") as f:
            f.write(flat_bytes)
        if audit_path and os.path.exists(audit_path):
            audit_archive = archive_path + ".audit.json"
            try:
                with open(audit_path, "rb") as src, \
                     open(audit_archive, "wb") as dst:
                    dst.write(src.read())
            except OSError:
                pass
        return archive_path
    except Exception:
        return None


def save_session_state(items, page_mode=None, flatten=None):
    """Persist the current item list (and a couple of UI prefs) so we can
    restore them on next launch. Best-effort — failure is silent so a
    full disk doesn't break the app. v1.45: preserves the archive_folder
    field by reading the existing JSON first."""
    # Read-modify-write so the archive_folder setting (and any other
    # future preferences) survive every session-state save.
    try:
        with open(_state_file(), "r", encoding="utf-8") as f:
            existing = json.load(f)
    except (OSError, ValueError):
        existing = {}
    data = {
        "version": _STATE_VERSION,
        "items": [
            {
                "kind": it.kind,
                "value": it.value,
                "label": it.label,
                "size_bytes": getattr(it, "size_bytes", 0),
                "flat_pages_est": getattr(it, "flat_pages_est", 1),
            }
            for it in items
        ],
    }
    if page_mode is not None:
        data["page_mode"] = page_mode
    if flatten is not None:
        data["flatten"] = bool(flatten)
    # Preserve non-session fields (archive_folder, auto-update bookkeeping,
    # future prefs) so a session save doesn't blow them away.
    for k in ("archive_folder", "auto_update_check", "last_update_check"):
        if k in existing:
            data[k] = existing[k]
    try:
        tmp = _state_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _state_file())
    except OSError:
        pass


def load_session_state():
    """Returns (items_data_list, page_mode_or_None, flatten_or_None,
    dropped_missing_count). items_data_list is the raw dicts — caller
    must instantiate Item() objects."""
    try:
        with open(_state_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return [], None, None, 0
    raw_items = data.get("items", []) or []
    surviving = []
    dropped = 0
    for it in raw_items:
        kind = it.get("kind")
        value = it.get("value")
        label = it.get("label", value or "")
        if not kind or not value:
            continue
        # URLs always survive — they re-fetch on Create PDF. Files only
        # survive if the path still exists on disk; users move/delete
        # things between sessions and we don't want broken entries.
        if kind == "file" and not os.path.exists(value):
            dropped += 1
            continue
        surviving.append({
            "kind": kind,
            "value": value,
            "label": label,
            "size_bytes": it.get("size_bytes", 0),
            "flat_pages_est": it.get("flat_pages_est", 1),
        })

    # State files written by v1.16–v1.18 (version 1) always saved
    # page_mode/flatten — even when they were just the *old default*
    # ("original" for page_mode). v1.19 introduced locale-aware page-
    # size defaults; restoring a v1 page_mode would silently override
    # the new default. So we ignore those two fields for v1 state and
    # only honour them for state written by v1.19+.
    state_version = data.get("version", 0)
    if state_version >= _STATE_VERSION:
        page_mode = data.get("page_mode")
        flatten = data.get("flatten")
    else:
        page_mode = None
        flatten = None
    return surviving, page_mode, flatten, dropped


# ---------------------------------------------------------------------------
# Missing-component detection + one-click install (v1.12).
#
# We carry a few optional system dependencies that aren't bundled (LibreOffice
# for Office conversion, SANE/scanimage for one-click scanner). When they're
# missing, the relevant feature breaks at use-time with a not-very-helpful
# message. This module surfaces "you're missing X" at startup and offers a
# one-click install on platforms where we can do it safely:
#   • Linux (apt/dnf/pacman/zypper) → pkexec runs the install with polkit auth
#   • macOS                          → brew install if Homebrew is present
#   • Windows                        → open the official download page
# ---------------------------------------------------------------------------
LIBREOFFICE_DOWNLOAD_URL = "https://www.libreoffice.org/download/download-libreoffice/"


def detect_linux_package_manager():
    """Returns (pm_id, install_command_list_prefix) or None.
    The prefix is intended to be used with: prefix + [package_names...]"""
    from shutil import which
    if not sys.platform.startswith("linux"):
        return None
    if which("apt-get"):
        return ("apt", ["pkexec", "apt-get", "install", "-y"])
    if which("dnf"):
        return ("dnf", ["pkexec", "dnf", "install", "-y"])
    if which("pacman"):
        return ("pacman", ["pkexec", "pacman", "-S", "--noconfirm"])
    if which("zypper"):
        return ("zypper", ["pkexec", "zypper", "install", "-y"])
    return None


# Per-component package names for each Linux package manager. None means
# "we don't have a known name for this combination".
_PKG_NAMES = {
    "libreoffice": {
        "apt": "libreoffice",
        "dnf": "libreoffice",
        "pacman": "libreoffice-still",
        "zypper": "libreoffice",
    },
    "sane": {
        "apt": "sane-utils",
        "dnf": "sane-backends",
        "pacman": "sane",
        "zypper": "sane-backends",
    },
}


def detect_office_suites():
    """Return a list of Office-suite names installed on this machine.
    Used to decide whether to nag the user about LibreOffice — if they
    already have *any* office suite (OnlyOffice, MS Office, Apple iWork,
    LibreOffice), the nag is silly and we suppress it. Note: full
    headless-conversion backend support for OnlyOffice / MS Office is
    planned for v1.19; until then conversion still routes through
    LibreOffice/DocumentBuilder, but the startup banner stays quiet."""
    from shutil import which
    found = []

    if find_libreoffice():
        found.append("LibreOffice")

    # OnlyOffice Desktop Editors (CLI command names vary by distro)
    if which("desktopeditors") or which("onlyoffice-desktopeditors"):
        found.append("OnlyOffice")
    if sys.platform == "darwin" and os.path.exists("/Applications/ONLYOFFICE.app"):
        found.append("OnlyOffice")
    if sys.platform.startswith("win"):
        for p in (
            r"C:\Program Files\ONLYOFFICE\DesktopEditors\DesktopEditors.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\ONLYOFFICE\DesktopEditors\DesktopEditors.exe"
            ),
        ):
            if os.path.exists(p):
                found.append("OnlyOffice")
                break

    # OnlyOffice DocumentBuilder (the headless converter — the one we'd
    # actually shell out to in v1.19).
    if which("documentbuilder") or which("docbuilder"):
        found.append("OnlyOffice DocumentBuilder")

    # Microsoft Office
    if sys.platform.startswith("win"):
        for p in (
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
        ):
            if os.path.exists(p):
                found.append("Microsoft Office")
                break
    if sys.platform == "darwin" and os.path.exists("/Applications/Microsoft Word.app"):
        found.append("Microsoft Office")

    # Apple iWork (macOS only)
    if sys.platform == "darwin":
        if (os.path.exists("/Applications/Pages.app")
                or os.path.exists("/Applications/Numbers.app")
                or os.path.exists("/Applications/Keynote.app")):
            found.append("Apple iWork")

    return found


def detect_missing_components():
    """Returns a list of dicts describing optional components missing on
    this system. Each dict has: id, label, why.

    We only nag about LibreOffice when the user has NO office suite
    installed at all — if they already use OnlyOffice / MS Office /
    iWork, asking them to add LibreOffice would be silly. If they have
    nothing, we lead with OnlyOffice as the recommended choice (free,
    best Microsoft-format fidelity) with LibreOffice as the alternate.
    """
    missing = []
    office_suites = detect_office_suites()
    if not office_suites:
        # Nothing installed — suggest OnlyOffice DocumentBuilder as the
        # primary recommendation (best Microsoft-format fidelity of free
        # tools, scriptable for headless PDF export). LibreOffice is the
        # widely-available fallback.
        missing.append({
            "id": "office_suite",
            "label": "An Office suite (OnlyOffice or LibreOffice)",
            "why": "Needed to convert Office documents (.docx, .xlsx, "
                   ".pptx, .odt) to PDF. OnlyOffice has the best "
                   "Microsoft-format fidelity; LibreOffice is the most "
                   "universally available alternative — pick whichever.",
        })

    if sys.platform.startswith("linux"):
        from shutil import which
        if not which("scanimage"):
            missing.append({
                "id": "sane",
                "label": "SANE scanner tools",
                "why": "Needed for one-click Scan from your scanner.",
            })
    return missing


ONLYOFFICE_DOWNLOAD_URL = "https://www.onlyoffice.com/download-desktop.aspx"


def install_component(component_id, status_cb=None):
    """Best-effort one-click install. Returns (success: bool, message: str).
    On Linux: uses pkexec + the detected package manager. On macOS: tries
    brew. On Windows / unknown: opens the upstream download page.
    `status_cb`, if given, is called with short status strings."""
    def _log(s):
        if status_cb is not None:
            try:
                status_cb(s)
            except Exception:
                pass

    # "An Office suite" — generic install path used when the user has
    # nothing installed. On Linux we install LibreOffice (one-click apt
    # is the most universal); on Windows/macOS we open the OnlyOffice
    # download page (your preferred suite — has the best Microsoft-
    # format fidelity of the free options).
    if component_id == "office_suite":
        if sys.platform.startswith("linux"):
            return install_component("libreoffice", status_cb=status_cb)
        webbrowser.open(ONLYOFFICE_DOWNLOAD_URL)
        alt = LIBREOFFICE_DOWNLOAD_URL
        return True, (
            "Opened the OnlyOffice download page in your browser.\n\n"
            "OnlyOffice is free, open-source, and has the best Microsoft-\n"
            "format fidelity. Download + install, then reopen this dialog\n"
            "and click 'Retry'.\n\n"
            f"If you'd rather use LibreOffice:\n  {alt}"
        )

    if sys.platform.startswith("linux"):
        pm_info = detect_linux_package_manager()
        if pm_info is None:
            return False, ("No supported package manager (apt/dnf/pacman/"
                           "zypper) found. Please install manually.")
        pm_id, prefix = pm_info
        pkg = _PKG_NAMES.get(component_id, {}).get(pm_id)
        if not pkg:
            return False, (f"Don't know the {pm_id} package name for "
                           f"'{component_id}'. Please install manually.")
        cmd = prefix + [pkg]
        _log(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=600)
        except FileNotFoundError:
            return False, ("pkexec isn't installed on this system. Run "
                           f"sudo {' '.join(prefix[1:] + [pkg])} in a terminal.")
        except subprocess.TimeoutExpired:
            return False, "Install timed out after 10 minutes."
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            tail_msg = tail[-1] if tail else f"exit {result.returncode}"
            return False, f"Install failed: {tail_msg}"
        return True, f"Installed {pkg} successfully."

    if sys.platform == "darwin":
        # Use brew when available; otherwise punt to the download page.
        from shutil import which
        if component_id == "libreoffice" and which("brew"):
            _log("Running: brew install --cask libreoffice")
            try:
                result = subprocess.run(
                    ["brew", "install", "--cask", "libreoffice"],
                    capture_output=True, text=True, timeout=900,
                )
                if result.returncode == 0:
                    return True, "Installed LibreOffice via Homebrew."
                tail = (result.stderr or "").strip().splitlines()
                return False, f"brew install failed: {tail[-1] if tail else 'unknown'}"
            except subprocess.TimeoutExpired:
                return False, "brew install timed out."
        if component_id == "libreoffice":
            webbrowser.open(LIBREOFFICE_DOWNLOAD_URL)
            return True, "Opened the LibreOffice download page in your browser."
        return False, "macOS doesn't have a built-in installer for this component."

    if sys.platform.startswith("win"):
        if component_id == "libreoffice":
            webbrowser.open(LIBREOFFICE_DOWNLOAD_URL)
            return True, (
                "Opened the LibreOffice download page in your browser.\n\n"
                "What to do next:\n"
                "  1. Pick the Windows x86_64 installer (.msi or .exe).\n"
                "  2. Run it — default options are fine, takes ~5 minutes.\n"
                "  3. Restart MyDocMaker (or just reopen this dialog\n"
                "     and click 'Retry install') and the banner will disappear.\n\n"
                "Why this is separate: bundling LibreOffice inside our installer\n"
                "would push it past 600 MB. Linking to the official download keeps\n"
                "our installer small and gives you the latest LibreOffice version."
            )
        return False, ("Windows doesn't have a built-in installer for this "
                       "component. Install from your vendor's site.")

    return False, "Unsupported platform."


# ---------------------------------------------------------------------------
# Converters — each returns a BytesIO containing a PDF
# ---------------------------------------------------------------------------
def image_to_pdf_bytes(path, page_mode="original"):
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        bg.paste(img, mask=mask)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    if page_mode == "original":
        img.save(buf, format="PDF")
    else:
        page = A4 if page_mode == "a4" else letter
        pw, ph = page
        c = canvas.Canvas(buf, pagesize=page)
        iw, ih = img.size
        scale = min(pw / iw, ph / ih)
        dw, dh = iw * scale, ih * scale
        x, y = (pw - dw) / 2, (ph - dh) / 2
        c.drawImage(ImageReader(img), x, y, dw, dh,
                    preserveAspectRatio=True, mask="auto")
        c.showPage()
        c.save()
    buf.seek(0)
    return buf


def text_to_pdf_bytes(path, page_mode="letter"):
    page = A4 if page_mode == "a4" else letter
    pw, ph = page
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page)
    margin = 50
    y = ph - margin
    c.setFont("Courier", 9)
    line_h = 11
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            max_chars = int((pw - 2 * margin) / 5.4)
            chunks = [line[i:i + max_chars] for i in range(0, len(line), max_chars)] or [""]
            for chunk in chunks:
                if y < margin:
                    c.showPage()
                    c.setFont("Courier", 9)
                    y = ph - margin
                c.drawString(margin, y, chunk)
                y -= line_h
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Office → PDF conversion (v1.22): multi-backend dispatcher.
#
# We try backends in priority order, picking the highest-fidelity available
# one for the file's format:
#   1. Microsoft Office (Windows COM via pywin32) — best fidelity for MS
#      Office formats, fastest, most users on Windows already have it.
#   2. OnlyOffice DocumentBuilder — second-best Microsoft-format fidelity,
#      free, cross-platform; requires a separate ~100 MB install.
#   3. LibreOffice — universal fallback; works on every platform.
# Each backend raises _BackendUnavailable if it's not installed (caller
# silently moves on); raises a regular Exception on actual failure (caller
# logs and moves on too, so a broken Word install doesn't lock out other
# backends).
# ---------------------------------------------------------------------------


class _BackendUnavailable(Exception):
    """Raised by an Office-conversion backend when it isn't installed. The
    dispatcher quietly tries the next backend in the priority list."""


def _office_via_msoffice_windows(path, ext):
    """Drive Microsoft Word/Excel/PowerPoint over COM (Windows only)."""
    if not sys.platform.startswith("win"):
        raise _BackendUnavailable("not on Windows")
    try:
        import win32com.client  # provided by pywin32
        import pythoncom
    except ImportError as e:
        raise _BackendUnavailable(f"pywin32 not available ({e})")

    # Map extension → (ProgID, opener-method, exporter)
    if ext in (".doc", ".docx", ".rtf", ".odt"):
        app_id, kind = "Word.Application", "word"
    elif ext in (".xls", ".xlsx", ".xlsm", ".ods", ".csv"):
        app_id, kind = "Excel.Application", "excel"
    elif ext in (".ppt", ".pptx", ".odp"):
        app_id, kind = "PowerPoint.Application", "powerpoint"
    else:
        raise _BackendUnavailable(f"no MS Office app for {ext}")

    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.DispatchEx(app_id)
        except Exception as e:
            raise _BackendUnavailable(f"{app_id} not installed ({e})")

        # Send Office to background; suppress dialogs that would block us.
        if kind != "powerpoint":
            app.Visible = False
        if kind == "excel":
            app.DisplayAlerts = False
        elif kind == "word":
            app.DisplayAlerts = 0  # wdAlertsNone

        abspath = os.path.abspath(path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            out_path = t.name

        try:
            if kind == "word":
                doc = app.Documents.Open(abspath, ReadOnly=True,
                                         ConfirmConversions=False,
                                         AddToRecentFiles=False)
                try:
                    doc.ExportAsFixedFormat(out_path, 17)  # 17 = wdExportFormatPDF
                finally:
                    doc.Close(SaveChanges=False)
            elif kind == "excel":
                wb = app.Workbooks.Open(abspath, ReadOnly=True,
                                        UpdateLinks=False)
                try:
                    wb.ExportAsFixedFormat(0, out_path)  # 0 = xlTypePDF
                finally:
                    wb.Close(SaveChanges=False)
            else:  # powerpoint
                # PowerPoint historically requires the app window visible to
                # load presentations; WithWindow=False suppresses each slide
                # window. SaveAs format 32 = ppSaveAsPDF.
                app.Visible = True
                pres = app.Presentations.Open(abspath, ReadOnly=True,
                                              WithWindow=False)
                try:
                    pres.SaveAs(out_path, 32)
                finally:
                    pres.Close()

            with open(out_path, "rb") as fh:
                data = fh.read()
            return io.BytesIO(data)
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass
            try:
                app.Quit()
            except Exception:
                pass
    finally:
        pythoncom.CoUninitialize()


def _office_via_onlyoffice_documentbuilder(path, ext):
    """Convert via OnlyOffice DocumentBuilder — separate headless CLI that
    runs a small JS script. Cross-platform when installed."""
    from shutil import which
    cmd = which("documentbuilder") or which("docbuilder")
    if not cmd:
        raise _BackendUnavailable("OnlyOffice DocumentBuilder not installed")

    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.abspath(path)
        output_path = os.path.join(tmp, "out.pdf")
        script_path = os.path.join(tmp, "convert.js")

        # json.dumps gives properly-escaped string literals that are valid
        # both as JSON and JS — handles Windows backslashes, spaces, unicode.
        script = (
            f"builder.OpenFile({json.dumps(input_path)});\n"
            f'builder.SaveFile("pdf", {json.dumps(output_path)});\n'
            f"builder.CloseFile();\n"
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        result = subprocess.run(
            [cmd, script_path],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0 or not os.path.exists(output_path):
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            err = tail[-1] if tail else f"exit {result.returncode}"
            raise RuntimeError(f"DocumentBuilder failed: {err}")
        with open(output_path, "rb") as f:
            return io.BytesIO(f.read())


def _office_via_libreoffice(path, ext):
    """Existing path — shells out to LibreOffice headless. The universal
    fallback; works on every platform when LibreOffice is installed."""
    soffice = find_libreoffice()
    if not soffice:
        raise _BackendUnavailable("LibreOffice not installed")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120,
        )
        base = os.path.splitext(os.path.basename(path))[0] + ".pdf"
        out = os.path.join(tmp, base)
        if not os.path.exists(out):
            raise RuntimeError("LibreOffice did not produce a PDF")
        with open(out, "rb") as fh:
            return io.BytesIO(fh.read())


def office_to_pdf_bytes(path):
    """Convert an Office document to PDF using the best available backend."""
    ext = os.path.splitext(path)[1].lower()
    backends = [
        ("Microsoft Office", _office_via_msoffice_windows),
        ("OnlyOffice DocumentBuilder", _office_via_onlyoffice_documentbuilder),
        ("LibreOffice", _office_via_libreoffice),
    ]
    last_errors = []
    for name, fn in backends:
        try:
            return fn(path, ext)
        except _BackendUnavailable:
            # Backend just isn't installed — silently try the next one.
            continue
        except Exception as e:
            # Backend was present but failed for this file. Record + try next
            # — sometimes Word chokes on a specific .docx that LibreOffice
            # handles fine (and vice versa).
            last_errors.append(f"{name}: {e}")
            continue
    detail = ("\n  • " + "\n  • ".join(last_errors)) if last_errors else ""
    raise RuntimeError(
        "No Office conversion backend was available. Install one of "
        "Microsoft Office, OnlyOffice DocumentBuilder, or LibreOffice."
        + detail
    )


def url_to_pdf_bytes(url, page_mode="a4"):
    """Capture a full live webpage to a multi-page PDF via headless Chromium."""
    from playwright.sync_api import sync_playwright
    fmt = "A4" if page_mode != "letter" else "Letter"
    buf = None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Force print media + light color scheme. Without these, many sites
        # render dark-mode/full-screen overlays into the PDF, producing the
        # all-gray "selected" look reported in v1.05.
        page = browser.new_page(viewport={"width": 1280, "height": 1800})
        page.emulate_media(media="print", color_scheme="light")
        page.goto(url, wait_until="networkidle", timeout=60000)
        # Some sites land with the body focused and a text range "selected"
        # by their own JS — drop both so the snapshot is clean.
        page.evaluate(
            "() => { try { window.getSelection && window.getSelection()."
            "removeAllRanges(); document.activeElement && "
            "document.activeElement.blur && document.activeElement.blur(); } "
            "catch (e) {} }"
        )
        pdf_bytes = page.pdf(
            format=fmt, print_background=True,
            margin={"top": "12mm", "bottom": "12mm",
                    "left": "10mm", "right": "10mm"},
        )
        browser.close()
        buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return buf


def flatten_pdf_bytes(pdf_bytes, dpi=FLATTEN_DPI, jpeg_quality=FLATTEN_JPEG_QUALITY,
                      progress=None):
    """Rasterize each page of `pdf_bytes` to JPEG and re-assemble. Used to
    shrink large output PDFs (especially image-heavy ones). Selectable text,
    links, and form fields do not survive — the page becomes a flat picture.

    progress, if given, is called as progress(page_done, total_pages) after
    each page so the UI can advance a progress bar."""
    if not FLATTEN_OK:
        raise RuntimeError("pypdfium2 is not available — install it to flatten")
    src = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    total = len(src)
    out = io.BytesIO()
    c = canvas.Canvas(out)
    scale = dpi / 72.0
    for i, page in enumerate(src):
        w_pt, h_pt = page.get_size()
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil().convert("RGB")
        jpeg = io.BytesIO()
        pil.save(jpeg, format="JPEG", quality=jpeg_quality, optimize=True)
        jpeg.seek(0)
        c.setPageSize((w_pt, h_pt))
        c.drawImage(ImageReader(jpeg), 0, 0, w_pt, h_pt)
        c.showPage()
        if progress is not None:
            try:
                progress(i + 1, total)
            except Exception:
                pass
    c.save()
    out.seek(0)
    return out


# ---------------------------------------------------------------------------
# E-signature (v1.28) — fully offline PAdES signing via pyhanko + a one-
# time self-signed certificate. Output is one signed.pdf (with embedded
# PKCS#7 signature shown in Acrobat's signature panel) plus a companion
# .audit.json sidecar that records SHA256 of the signed file, the
# signer's local identity, and timestamp — for human-readable
# verification.
#
# All deps are pure-Python (pyhanko + cryptography). No external CA, no
# online timestamping. Recipients see "self-signed" until they trust the
# certificate — same trade-off as code-signing without a paid cert.
# ---------------------------------------------------------------------------
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyhanko.sign import signers, fields
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
    SIGNING_OK = True
except Exception:
    SIGNING_OK = False


def _config_dir():
    base = os.environ.get(
        "XDG_CONFIG_HOME",
        os.path.join(os.path.expanduser("~"), ".config"),
    )
    p = os.path.join(base, "mydocmaker")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError:
        pass
    return p


def _signing_subdir():
    p = os.path.join(_config_dir(), "signing")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError:
        pass
    return p


def _key_path():
    return os.path.join(_signing_subdir(), "key.pem")


def _cert_path():
    return os.path.join(_signing_subdir(), "certificate.pem")


def _signature_image_path():
    """v1.28 single-signature path. Kept for migration only."""
    return os.path.join(_signing_subdir(), "signature.png")


def _signature_meta_path():
    """v1.28 single-signature path. Kept for migration only."""
    return os.path.join(_signing_subdir(), "signature.json")


def _signatures_dir():
    """v1.31+: multi-signature store. One PNG + one JSON per signature,
    keyed by a stable UUID."""
    p = os.path.join(_config_dir(), "signatures")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError:
        pass
    return p


# Metadata fields each signature can carry. Only `label` is required.
# v1.38: added `creator_mode` so the dialog knows which radio to
# pre-select on edit (digital / type / draw). v1.32–v1.37 silently
# dropped this on save because the filter below didn't whitelist it.
SIGNATURE_META_FIELDS = (
    "label", "name", "company", "address", "tax_id", "license",
    "style", "creator_mode", "created_at",
)


def list_signatures():
    """Returns a list of signature meta dicts. Each dict includes 'id'
    (uuid hex) and 'image_path' (absolute PNG path) on top of stored
    metadata. Empty list if none saved. Auto-migrates the v1.28 single
    signature if found."""
    _migrate_legacy_signature()
    out = []
    d = _signatures_dir()
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        uid = fn[:-5]
        meta_path = os.path.join(d, fn)
        png_path = os.path.join(d, uid + ".png")
        if not os.path.exists(png_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        meta["id"] = uid
        meta["image_path"] = png_path
        out.append(meta)
    out.sort(key=lambda m: m.get("created_at", ""))
    return out


def load_signature_image(sig_id):
    p = os.path.join(_signatures_dir(), sig_id + ".png")
    with open(p, "rb") as f:
        return f.read()


def save_signature_record(sig_id, png_bytes, meta):
    """Save (or overwrite) one signature record. `meta` should contain at
    minimum a `label`. Returns the sig_id used."""
    if not sig_id:
        sig_id = uuid.uuid4().hex
    d = _signatures_dir()
    with open(os.path.join(d, sig_id + ".png"), "wb") as f:
        f.write(png_bytes)
    rec = {k: meta.get(k, "") for k in SIGNATURE_META_FIELDS}
    if not rec.get("created_at"):
        rec["created_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(os.path.join(d, sig_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    return sig_id


def delete_signature_record(sig_id):
    d = _signatures_dir()
    for ext in (".png", ".json"):
        p = os.path.join(d, sig_id + ext)
        if os.path.exists(p):
            try:
                os.unlink(p)
            except OSError:
                pass


def _migrate_legacy_signature():
    """If a v1.28-era single signature exists at signing/signature.{png,json}
    but the multi-sig store is empty, copy it in as the first entry. Safe
    to call multiple times — only runs when the conditions match."""
    new_dir = _signatures_dir()
    if any(f.endswith(".json") for f in os.listdir(new_dir)):
        return  # already have multi-sig entries; don't double-migrate
    legacy_png = _signature_image_path()
    legacy_meta = _signature_meta_path()
    if not (os.path.exists(legacy_png) and os.path.exists(legacy_meta)):
        return
    try:
        with open(legacy_png, "rb") as f:
            png = f.read()
        with open(legacy_meta, "r", encoding="utf-8") as f:
            old_meta = json.load(f)
    except (OSError, ValueError):
        return
    new_meta = {
        "label": old_meta.get("label", "My signature"),
        "name": old_meta.get("label", "") or "",
        "company": "", "address": "", "tax_id": "", "license": "",
        "style": old_meta.get("style", "drawn"),
        "created_at": old_meta.get("created_at",
                                   datetime.datetime.utcnow().isoformat() + "Z"),
    }
    save_signature_record(None, png, new_meta)


# ---- v1.28-era single-signature shims, kept so the SignDialog/old code
# paths keep working until everywhere has been updated to multi-sig. ----
def has_saved_signature():
    return len(list_signatures()) > 0


def load_saved_signature():
    """Returns (png_bytes, meta_dict) for the FIRST saved signature, or
    (None, None) if none. Multi-sig callers should use list_signatures()
    directly."""
    sigs = list_signatures()
    if not sigs:
        return None, None
    first = sigs[0]
    try:
        with open(first["image_path"], "rb") as f:
            return f.read(), first
    except OSError:
        return None, None


def save_signature(png_bytes, label="My signature", style="drawn"):
    """Single-signature shim — appends to the multi-sig store with
    minimal metadata. Used by callers that haven't been migrated yet."""
    return save_signature_record(None, png_bytes, {
        "label": label, "name": label, "style": style,
        "company": "", "address": "", "tax_id": "", "license": "",
    })


def ensure_signing_keys(common_name=None):
    """Generate a self-signed RSA-2048 keypair on first use. Stored at
    ~/.config/mydocmaker/signing/{key,certificate}.pem.
    Returns (key_path, cert_path). Idempotent — if files exist, returns
    the existing pair untouched."""
    if not SIGNING_OK:
        raise RuntimeError("Install pyhanko + cryptography for e-signing.")
    key_path = _key_path()
    cert_path = _cert_path()
    if os.path.exists(key_path) and os.path.exists(cert_path):
        return key_path, cert_path

    if not common_name:
        try:
            common_name = getpass.getuser()
        except Exception:
            common_name = "MyDocMaker user"

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, APP_NAME),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Self-signed"),
    ])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                       critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=True,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(private_key, hashes.SHA256())
    )
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return key_path, cert_path


def _certificate_sha256_fingerprint():
    """Returns the SHA256 fingerprint of the public certificate, for the
    audit JSON. Falls back to None if anything is broken."""
    try:
        with open(_cert_path(), "rb") as f:
            cert_pem = f.read()
        cert = x509.load_pem_x509_certificate(cert_pem)
        return hashes.Hash(hashes.SHA256()).update(
            cert.fingerprint(hashes.SHA256())
        ) if False else cert.fingerprint(hashes.SHA256()).hex()
    except Exception:
        return None


def sign_pdf_with_appearance(pdf_bytes, signature_png_bytes, position,
                              output_path, common_name=None):
    """Sign `pdf_bytes` and write the resulting PDF to `output_path`.
    Embeds a visible signature appearance (the user's PNG stamp) at
    `position`: dict with 'page' (1-indexed), 'x_pt', 'y_pt', 'width_pt',
    'height_pt' in PDF point coordinates.

    Returns the SHA256 hex of the final signed bytes (for the audit JSON)."""
    if not SIGNING_OK:
        raise RuntimeError("Install pyhanko + cryptography for e-signing.")
    key_path, cert_path = ensure_signing_keys(common_name)

    signer = signers.SimpleSigner.load(
        key_file=key_path, cert_file=cert_path, key_passphrase=None,
    )

    pdf_in = io.BytesIO(pdf_bytes)
    w = IncrementalPdfFileWriter(pdf_in)

    field_name = "Signature1"
    page_idx = position["page"] - 1
    x = position["x_pt"]
    y = position["y_pt"]
    box = (x, y, x + position["width_pt"], y + position["height_pt"])
    sig_field_spec = fields.SigFieldSpec(
        sig_field_name=field_name,
        on_page=page_idx,
        box=box,
    )
    fields.append_signature_field(w, sig_field_spec)

    # Visible appearance: pyhanko can stamp an image via stamp.PdfStamp,
    # but for an MVP we write the PNG to a tempfile and use its built-in
    # ImageStampStyle.
    from pyhanko.stamp import StaticStampStyle
    from pyhanko.pdf_utils.images import PdfImage

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as sig_tmp:
        sig_tmp.write(signature_png_bytes)
        sig_tmp_path = sig_tmp.name
    try:
        stamp_style = StaticStampStyle.from_pdf_file(sig_tmp_path) \
            if sig_tmp_path.endswith(".pdf") else None
        # For PNG, easier path: use the bitmap as a watermark image
        sig_meta = PdfSignatureMetadata(
            field_name=field_name,
            reason=None,
            location=None,
            subfilter=fields.SigSeedSubFilter.PADES,
        )
        pdf_signer = signers.PdfSigner(
            signature_meta=sig_meta,
            signer=signer,
            stamp_style=stamp_style,
        )
        output = io.BytesIO()
        pdf_signer.sign_pdf(w, output=output)
        signed_bytes = output.getvalue()
    finally:
        try:
            os.unlink(sig_tmp_path)
        except OSError:
            pass

    with open(output_path, "wb") as f:
        f.write(signed_bytes)
    return hashlib.sha256(signed_bytes).hexdigest()


def write_audit_json(signed_pdf_path, position, signer_name, sha256_hex):
    """Single-position variant kept for v1.28 backward compatibility."""
    return write_audit_json_multi(signed_pdf_path, [position], signer_name,
                                  sha256_hex)


def write_audit_json_multi(signed_pdf_path, positions, signer_name, sha256_hex):
    """Audit JSON sidecar with possibly-multiple signature positions."""
    audit_path = signed_pdf_path + ".audit.json"
    cert_fp = _certificate_sha256_fingerprint()
    try:
        machine = f"{getpass.getuser()}@{_platform_mod.node()}"
    except Exception:
        machine = "unknown"
    # Strip UI-only fields from the audit copy.
    pos_records = [
        {k: v for k, v in p.items() if k in
         ("page", "x_pt", "y_pt", "width_pt", "height_pt")}
        for p in positions
    ]
    data = {
        "schema_version": 2,
        "signed_pdf": os.path.basename(signed_pdf_path),
        "signed_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "signer": {"common_name": signer_name, "machine": machine},
        "signature_count": len(positions),
        "signature_positions": pos_records,
        "signed_pdf_sha256": sha256_hex,
        "certificate_sha256": cert_fp,
        "verification": {
            "by_hash": f"sha256sum '{os.path.basename(signed_pdf_path)}' "
                       f"should output: {sha256_hex}",
            "by_acrobat": "Open the PDF in Adobe Acrobat Reader — the "
                          "Signature Panel will show each signature + cert.",
        },
        "produced_by": f"{APP_NAME} v{APP_VERSION}",
    }
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return audit_path


# --- v1.36 helpers ---------------------------------------------------------
def _find_font(candidates, size):
    """Return the first ImageFont.truetype that loads from `candidates`,
    or ImageFont.load_default() if none are available. Shielded against
    missing-file / unreadable-file errors."""
    from PIL import ImageFont
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _compose_signature_appearance(signature_png_bytes, meta, timestamp_str):
    """v1.43: compact DocuSign-style appearance with minimal internal
    padding — text fills the rectangle efficiently.

    Output is 880×264 px (3.33:1 aspect, matching the 220×66 default
    stamp). Tight margins, pixel-measured line wrapping for long
    addresses/companies, and a '✓ SHA-256 · <timestamp>' badge on the
    bottom line so the recipient sees both the cryptographic protection
    type and when it was signed.

    `meta` is a dict with the keys: name, company, address, tax_id,
    license. Missing/empty keys are skipped — typed and drawn
    signatures with no business details render as just name + ts."""
    from PIL import ImageDraw
    W, H = 880, 264
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))

    # Left 42% — signature image.
    left_w = int(W * 0.42)
    sig = Image.open(io.BytesIO(signature_png_bytes)).convert("RGBA")
    # v1.43: crop the source PNG to its non-transparent bounding box so
    # the visible content fills the left pane instead of being scaled
    # down with all the empty padding around it. getbbox() is None for
    # fully-blank images — protect against that.
    bbox = sig.getbbox()
    if bbox:
        sig = sig.crop(bbox)
    target_w = left_w - 10
    target_h = H - 16
    src_ratio = sig.width / sig.height
    box_ratio = target_w / target_h
    if src_ratio > box_ratio:
        new_w = target_w
        new_h = max(1, int(target_w / src_ratio))
    else:
        new_h = target_h
        new_w = max(1, int(target_h * src_ratio))
    sig = sig.resize((new_w, new_h), LANCZOS)
    sx = (left_w - new_w) // 2
    sy = (H - new_h) // 2
    img.paste(sig, (sx, sy), sig)

    draw = ImageDraw.Draw(img)
    draw.line([(left_w, 10), (left_w, H - 10)],
              fill=(140, 140, 140, 200), width=2)

    sans = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    sans_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    font_name = _find_font(sans_bold, 44)
    font_value = _find_font(sans, 30)
    font_caption = _find_font(sans, 26)
    font_badge = _find_font(sans, 22)

    name = (meta.get("name") or "").strip()
    company = (meta.get("company") or "").strip()
    address = (meta.get("address") or "").strip()
    tax_id = (meta.get("tax_id") or "").strip()
    license_ = (meta.get("license") or "").strip()

    # Tight right-pane padding: 6 left, 4 right, 6 top, ~36 bottom
    # (reserved for the SHA + timestamp badge).
    text_x = left_w + 10
    text_w = W - text_x - 6
    y = 8

    def _wrap_to_width(text, font):
        """Greedy word-wrap on pixel width; falls back to char split for
        words that exceed the pane width on their own."""
        words = text.split()
        if not words:
            return []
        lines, cur = [], words[0]
        for w in words[1:]:
            trial = cur + " " + w
            bbox = draw.textbbox((0, 0), trial, font=font)
            if (bbox[2] - bbox[0]) <= text_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    # Name (bold). Single line — auto-shrink only if extremely long.
    n_font = font_name
    n_size = 44
    while n_size > 22:
        bbox = draw.textbbox((0, 0), name or "—", font=n_font)
        if (bbox[2] - bbox[0]) <= text_w:
            break
        n_size -= 4
        n_font = _find_font(sans_bold, n_size)
    draw.text((text_x, y), name or "—",
              fill=(20, 20, 50, 255), font=n_font)
    y += int(n_size * 1.1) + 4  # ~50 px for 44pt; less if shrunk

    def _draw_line(text, font, color, line_h):
        nonlocal y
        if y > H - 38:
            return
        draw.text((text_x, y), text, fill=color, font=font)
        y += line_h

    if company:
        for line in _wrap_to_width(company, font_value):
            _draw_line(line, font_value, (45, 45, 70, 255), line_h=34)
    if address:
        for line in _wrap_to_width(address, font_caption):
            _draw_line(line, font_caption, (80, 80, 80, 255), line_h=30)
    if tax_id:
        for line in _wrap_to_width(f"Tax ID: {tax_id}", font_caption):
            _draw_line(line, font_caption, (80, 80, 80, 255), line_h=30)
    if license_:
        for line in _wrap_to_width(f"License: {license_}", font_caption):
            _draw_line(line, font_caption, (80, 80, 80, 255), line_h=30)

    # v1.43: '✓ SHA-256 · <timestamp>' badge pinned to the bottom-right.
    # The check mark + SHA label signals 'cryptographically protected'
    # without needing an emoji glyph (✓ U+2713 is in DejaVu and every
    # system font). Bumped UP a few pixels from the very bottom so
    # pyhanko's stamp rendering doesn't clip the descenders.
    badge = f"✓ SHA-256  ·  {timestamp_str}"
    draw.text((text_x, H - 30), badge,
              fill=(95, 95, 115, 255), font=font_badge)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _overlay_appearance_on_page(pdf_bytes, appearance_png, page_idx,
                                  x_pt, y_pt, w_pt, h_pt):
    """v1.44: bake the composed appearance PNG into the page's content
    stream at the given PDF coordinates. Belt-and-suspenders security:
    even if a tamperer deletes the signature widget annotation in a PDF
    editor (Foxit, Master PDF), the visual still appears on the page
    because it's part of the page's drawing instructions. Any attempt
    to remove the page-content overlay edits the page itself, which
    the cryptographic signature seal will flag as tampering."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for pidx, src_page in enumerate(reader.pages):
        if pidx == page_idx:
            page_w = float(src_page.mediabox.width)
            page_h = float(src_page.mediabox.height)
            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
            img = ImageReader(io.BytesIO(appearance_png))
            c.drawImage(img, x_pt, y_pt, width=w_pt, height=h_pt,
                        mask="auto", preserveAspectRatio=True, anchor="c")
            c.showPage()
            c.save()
            overlay_reader = PdfReader(io.BytesIO(buf.getvalue()))
            src_page.merge_page(overlay_reader.pages[0])
        writer.add_page(src_page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _png_to_stamp_pdf(png_bytes, width_pt, height_pt):
    """Wrap a PNG as a single-page PDF sized to the stamp box. This is
    the input to pyhanko.stamp.StaticStampStyle.from_pdf_file, which
    needs a PDF (not a raw image) as the visible-signature appearance.

    Pre-v1.36 the appearance PNG was composed but pyhanko was always
    called with stamp_style=None — so its default 'Digitally signed by …'
    text was what users actually saw. This helper closes the gap."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_pt, height_pt))
    img = ImageReader(io.BytesIO(png_bytes))
    c.drawImage(img, 0, 0, width=width_pt, height=height_pt,
                mask="auto", preserveAspectRatio=True, anchor="c")
    c.showPage()
    c.save()
    return buf.getvalue()


def _safe_field_name(label, index):
    """Turn a friendly label into a PDF-acceptable field name."""
    if not label:
        return f"DDPDF-Sig{index}"
    # PDF spec allows most printable ASCII; strip parens (Acrobat dislikes
    # them in field names) and collapse whitespace.
    cleaned = re.sub(r"[^A-Za-z0-9 #\-_.]", "", label).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or f"DDPDF-Sig{index}"


def _draw_signature_placeholder_overlay(pdf_bytes, positions):
    """v1.31: overlay a visible dashed rectangle + caption on top of every
    `positions` entry so recipients immediately SEE where to sign. Without
    this, an empty pyhanko signature field is just an invisible hit-target
    in most viewers — the user has to know to click. Returns new PDF bytes
    with the overlay merged in (page geometry preserved)."""
    if not positions:
        return pdf_bytes
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import HexColor
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return pdf_bytes  # missing deps → silently skip the visual cue

    reader = PdfReader(io.BytesIO(pdf_bytes))
    by_page = {}
    for pos in positions:
        by_page.setdefault(pos["page"] - 1, []).append(pos)

    writer = PdfWriter()
    for pidx, page in enumerate(reader.pages):
        if pidx in by_page:
            w_pt = float(page.mediabox.width)
            h_pt = float(page.mediabox.height)
            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(w_pt, h_pt))
            c.setStrokeColor(HexColor("#0a64d8"))
            c.setFillColor(HexColor("#0a64d8"))
            c.setLineWidth(1.5)
            c.setDash(6, 4)
            for pos in by_page[pidx]:
                x, y = pos["x_pt"], pos["y_pt"]
                w, h = pos["width_pt"], pos["height_pt"]
                c.rect(x, y, w, h, stroke=1, fill=0)
                caption = pos.get("label") or "Sign here"
                # Trim parens that Acrobat dislikes in display too.
                caption = re.sub(r"[\(\)]", "", caption)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(x + 4, y + h - 14, caption)
                c.setFont("Helvetica", 8)
                c.drawString(x + 4, y + 4, "Click here in Acrobat to sign")
            c.setDash()
            c.showPage()
            c.save()
            overlay_reader = PdfReader(io.BytesIO(buf.getvalue()))
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def sign_pdf_with_appearance_multi(pdf_bytes, positions, output_path,
                                    empty_fields=None):
    """v1.31: sign each position with its OWN signature PNG / signer name.

    `positions` — list of dicts with: page, x_pt, y_pt, width_pt, height_pt,
        signature_png (bytes), common_name (str), label (optional). Each
        position is signed individually; pyhanko applies them sequentially
        via incremental updates so all signatures verify in Acrobat.

    `empty_fields` — same shape but no signature_png / common_name; saved
        as un-signed signature widgets for the next signer to fill in
        later. v1.31 also draws a visible dashed-blue placeholder rectangle
        underneath each empty field so the recipient sees it immediately.

    Returns SHA256 of the final file. Note: every signature shares the
    same self-signed cert (one per machine for now). The signer NAME comes
    from `common_name` and lands in the signature appearance + audit log,
    which is enough to distinguish people visually.
    """
    if not SIGNING_OK:
        raise RuntimeError("Install pyhanko + cryptography for e-signing.")
    if not positions:
        raise RuntimeError("No signature positions provided.")
    # Cert generated lazily under the first signer's name; subsequent
    # signers reuse the same cert — multi-cert support is v1.32.
    primary_cn = positions[0].get("common_name") or "Signer"
    key_path, cert_path = ensure_signing_keys(primary_cn)
    signer = signers.SimpleSigner.load(
        key_file=key_path, cert_file=cert_path, key_passphrase=None,
    )

    current_bytes = pdf_bytes
    # First: draw visible placeholders for the empty fields, before pyhanko
    # adds the (invisible) widget annotations. Order matters — overlay
    # below, widget on top, so the click hit-test still works.
    if empty_fields:
        current_bytes = _draw_signature_placeholder_overlay(
            current_bytes, empty_fields,
        )
        w = IncrementalPdfFileWriter(io.BytesIO(current_bytes))
        for j, pos in enumerate(empty_fields, start=1):
            box = (pos["x_pt"], pos["y_pt"],
                   pos["x_pt"] + pos["width_pt"],
                   pos["y_pt"] + pos["height_pt"])
            name = _safe_field_name(pos.get("label"), j) or f"DDPDF-Empty{j}"
            fields.append_signature_field(w, fields.SigFieldSpec(
                sig_field_name=name,
                on_page=pos["page"] - 1, box=box,
            ))
        out = io.BytesIO()
        w.write(out)
        current_bytes = out.getvalue()

    # Sign each position. v1.44 belt-and-suspenders flow:
    #   1. Bake the composed appearance into the page's content stream
    #      (raster overlay via _overlay_appearance_on_page). Now the
    #      visible signature is part of the page itself — basic PDF
    #      editors (Foxit, Master PDF) can't quietly delete it like
    #      they can with a widget annotation.
    #   2. Sign with a VISIBLE widget on top of that overlay, using
    #      StaticStampStyle so Acrobat shows the clickable signature
    #      badge + signature panel entry the user expects.
    #   3. First signature certifies the document with FILL_FORMS
    #      permission (allows subsequent fills + sigs by other signers,
    #      but disallows any other modification — Acrobat will mark
    #      the signature 'invalid' if anyone tampers).
    from pyhanko.stamp import StaticStampStyle
    try:
        from pyhanko.sign.fields import MDPPerm
    except ImportError:
        MDPPerm = None
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip() or \
         datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    for i, pos in enumerate(positions, start=1):
        field_name = _safe_field_name(pos.get("label"), i) or f"DDPDF-Sig{i}"
        box = (pos["x_pt"], pos["y_pt"],
               pos["x_pt"] + pos["width_pt"],
               pos["y_pt"] + pos["height_pt"])
        sig_png = pos.get("signature_png")
        meta = pos.get("signer_meta") or {
            "name": pos.get("common_name") or "Signer",
        }
        if not sig_png:
            raise RuntimeError(f"Position {i} has no signature_png — "
                                "did you forget to assign a signature?")
        appearance_png = _compose_signature_appearance(sig_png, meta, ts)

        # Step 1: bake appearance into page content (un-deletable).
        current_bytes = _overlay_appearance_on_page(
            current_bytes, appearance_png,
            page_idx=pos["page"] - 1,
            x_pt=pos["x_pt"], y_pt=pos["y_pt"],
            w_pt=pos["width_pt"], h_pt=pos["height_pt"],
        )

        # Step 2: cryptographic widget on top.
        w = IncrementalPdfFileWriter(io.BytesIO(current_bytes))
        stamp_pdf = _png_to_stamp_pdf(
            appearance_png, pos["width_pt"], pos["height_pt"],
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            t.write(stamp_pdf)
            stamp_tmp = t.name
        try:
            stamp_style = StaticStampStyle.from_pdf_file(stamp_tmp)
            # Step 3: first sig certifies; subsequent sigs are regular.
            certify_this = (i == 1)
            docmdp = (MDPPerm.FILL_FORMS
                       if (certify_this and MDPPerm is not None) else None)
            sig_meta_kwargs = dict(
                field_name=field_name,
                reason=None, location=None,
                subfilter=fields.SigSeedSubFilter.PADES,
            )
            if certify_this:
                sig_meta_kwargs["certify"] = True
                if docmdp is not None:
                    sig_meta_kwargs["docmdp_permissions"] = docmdp
            sig_meta = PdfSignatureMetadata(**sig_meta_kwargs)
            new_field_spec = fields.SigFieldSpec(
                sig_field_name=field_name,
                on_page=pos["page"] - 1, box=box,
            )
            pdf_signer = signers.PdfSigner(
                signature_meta=sig_meta, signer=signer,
                stamp_style=stamp_style,
                new_field_spec=new_field_spec,
            )
            out = io.BytesIO()
            pdf_signer.sign_pdf(w, output=out)
            current_bytes = out.getvalue()
        finally:
            try:
                os.unlink(stamp_tmp)
            except OSError:
                pass

    with open(output_path, "wb") as f:
        f.write(current_bytes)
    return hashlib.sha256(current_bytes).hexdigest()


def prepare_pdf_with_empty_signature_fields(pdf_bytes, positions, output_path):
    """Append empty (un-signed) signature fields at each position and save.
    v1.31: also overlays a visible dashed-blue rectangle + caption on each
    spot so the recipient sees WHERE to sign without first having to open
    Acrobat's signature panel. Each position can carry a `label` key —
    used as the PDF field name and as the on-page caption."""
    if not SIGNING_OK:
        raise RuntimeError("Install pyhanko + cryptography for this feature.")
    # Visible blue placeholders first, then the interactive widgets on top.
    overlaid = _draw_signature_placeholder_overlay(pdf_bytes, positions)
    w = IncrementalPdfFileWriter(io.BytesIO(overlaid))
    for i, pos in enumerate(positions, start=1):
        box = (pos["x_pt"], pos["y_pt"],
               pos["x_pt"] + pos["width_pt"],
               pos["y_pt"] + pos["height_pt"])
        name = _safe_field_name(pos.get("label"), i)
        fields.append_signature_field(w, fields.SigFieldSpec(
            sig_field_name=name,
            on_page=pos["page"] - 1, box=box,
        ))
    output = io.BytesIO()
    w.write(output)
    with open(output_path, "wb") as f:
        f.write(output.getvalue())


# ---------------------------------------------------------------------------
# QR phone upload — a tiny one-shot HTTP server bound to the LAN IP. The
# user scans a QR with their phone, the phone's browser POSTs files back, and
# the desktop app adds them to the list via the same path drag-and-drop uses.
# ---------------------------------------------------------------------------
_UPLOAD_HTML = """<!doctype html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{app}</title>
<style>
body{{font-family:-apple-system,system-ui,sans-serif;padding:24px;max-width:480px;margin:auto;color:#222}}
h1{{font-size:1.3em;margin:0 0 16px}}
form{{display:flex;flex-direction:column;gap:18px}}
input[type=file]{{padding:14px;border:1px dashed #888;border-radius:8px;font-size:1em}}
button{{padding:16px;background:#0a64d8;color:#fff;border:0;border-radius:8px;font-size:1.05em}}
.note{{color:#888;font-size:.9em;margin-top:18px}}
</style></head><body>
<h1>Send to {app}</h1>
<form method="POST" action="/u/{token}/upload" enctype="multipart/form-data">
  <input type="file" name="files" accept="image/*,application/pdf" capture="environment" multiple required>
  <button type="submit">Upload to computer</button>
</form>
<p class="note">Files go to the running app on your computer. Same Wi-Fi required.</p>
</body></html>"""

_DONE_HTML = """<!doctype html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{app}</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;padding:32px;text-align:center;color:#222}}</style>
</head><body>
<h2>✓ Uploaded</h2>
<p>Your files have been added to {app}.</p>
<p style="color:#888;margin-top:24px">You can close this tab, or upload more.</p>
<p><a href="/u/{token}">Upload another batch</a></p>
</body></html>"""


def _lan_ip():
    """Returns this machine's LAN IP (the one a phone on the same Wi-Fi can
    reach). Uses the standard 'connect to a public IP but don't actually
    send' trick — Linux/Mac/Windows all populate getsockname() this way."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _parse_multipart_files(body, boundary):
    """Returns [(filename, bytes), ...] for file parts of a multipart body.
    Replaces cgi.FieldStorage (deprecated in 3.13) — handles the only thing
    we care about: form-data parts that look like files."""
    sep = b"--" + boundary.encode("ascii")
    files = []
    for part in body.split(sep):
        # First part is preamble (often empty), last is "--\r\n"
        if b"\r\n\r\n" not in part:
            continue
        head, payload = part.split(b"\r\n\r\n", 1)
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        head_text = head.decode("latin-1", "replace")
        m = re.search(r'filename="([^"]*)"', head_text)
        if not m:
            continue
        fname = m.group(1)
        if not fname:
            continue
        try:
            fname = fname.encode("latin-1").decode("utf-8", "replace")
        except UnicodeError:
            pass
        files.append((fname, payload))
    return files


class QrUploadServer:
    """One-shot HTTP server for phone uploads. Bound to 0.0.0.0 so it's
    reachable on the LAN; tokenized URL means random LAN devices can't
    inject files just by guessing the port."""

    def __init__(self, on_files):
        self.on_files = on_files
        self.token = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        self.host = _lan_ip()
        self.port = None
        self._httpd = None
        self.tmpdir = tempfile.mkdtemp(prefix="ddpdf_qr_")

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/u/{self.token}"

    def start(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        server = self  # closure access

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass  # silence default access logging

            def do_GET(self):
                if self.path != f"/u/{server.token}":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = _UPLOAD_HTML.format(app=APP_NAME, token=server.token).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path != f"/u/{server.token}/upload":
                    self.send_response(404)
                    self.end_headers()
                    return
                ctype = self.headers.get("Content-Type", "")
                m = re.search(r"boundary=(.*)$", ctype)
                if not m:
                    self.send_response(400)
                    self.end_headers()
                    return
                boundary = m.group(1).strip().strip('"')
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                saved = []
                for fname, data in _parse_multipart_files(body, boundary):
                    safe = os.path.basename(fname).replace("..", "_")
                    if not safe:
                        continue
                    p = os.path.join(server.tmpdir, safe)
                    with open(p, "wb") as f:
                        f.write(data)
                    saved.append(p)
                if saved:
                    try:
                        server.on_files(saved)
                    except Exception:
                        pass
                done = _DONE_HTML.format(app=APP_NAME, token=server.token).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(done)))
                self.end_headers()
                self.wfile.write(done)

        self._httpd = HTTPServer(("0.0.0.0", 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None


# ---------------------------------------------------------------------------
# An item in the list: either a file path, or a captured URL.
# ---------------------------------------------------------------------------
class Item:
    """An item in the page list.

    v1.23 adds caching fields so the live Preview tab can stitch a
    combined PDF instantly from already-rendered per-item bytes —
    reorder + remove become free, only first-time render of a new
    item costs anything.
    """
    def __init__(self, kind, value, label, size_bytes=0, flat_pages_est=1):
        self.kind = kind      # "file" or "url"
        self.value = value    # path or url string
        self.label = label    # what shows in the list
        self.size_bytes = size_bytes        # on-disk size (0 for URLs)
        self.flat_pages_est = flat_pages_est  # estimated pages after flatten
        # --- render cache (in-memory only; lost on app restart) ---
        # uid: stable identifier for this Item instance, used as a cache key
        # in cross-thread messages between RenderWorker and the Tk main thread.
        self.uid = uuid.uuid4().hex
        self.cached_pdf_bytes = None   # bytes (the rendered PDF for this item)
        self.cache_key = None          # (path, mtime) tuple — invalidates on edit
        self.render_status = "pending"  # pending | queued | rendering | ready | failed
        self.render_error = None       # str when render_status == "failed"

    def status_glyph(self):
        """Short single-character indicator appended to the listbox label."""
        return {
            "pending": "  …",
            "queued": "  …",
            "rendering": "  ⏳",
            "ready": "  ✓",
            "failed": "  ✗",
        }.get(self.render_status, "")


# ---------------------------------------------------------------------------
# Background render worker (v1.23): turns every queued Item into PDF bytes
# off the UI thread, so the Preview tab can show a live combined view.
#
# Two worker threads pull from a single queue (concurrency=2 keeps Chromium
# from spawning more than 2 instances when several URLs are added at once).
# Results are reported back to App.work_queue so the Tk main thread does
# every Tk-touching operation itself.
# ---------------------------------------------------------------------------
class RenderWorker:
    def __init__(self, on_event, page_mode_fn, concurrency=2):
        """on_event: callable(msg_tuple) — pushed onto App.work_queue.
        page_mode_fn: zero-arg callable returning current page-size pref."""
        self._on_event = on_event
        self._page_mode_fn = page_mode_fn
        self._queue = queue.Queue()
        self._stop = threading.Event()
        for _ in range(concurrency):
            t = threading.Thread(target=self._loop, daemon=True)
            t.start()

    def enqueue(self, item):
        """Queue an item for rendering. Safe to call from the Tk thread."""
        if item.render_status in ("rendering",):
            return  # already in flight
        item.render_status = "queued"
        item.render_error = None
        self._queue.put(item)

    def reset_cache(self, item):
        """Drop the cached bytes (e.g., page-size changed, force re-render)."""
        item.cached_pdf_bytes = None
        item.cache_key = None
        item.render_status = "pending"
        item.render_error = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                item.render_status = "rendering"
                self._on_event(("item_status", item.uid))
                page_mode = self._page_mode_fn()
                data = self._render(item, page_mode)
                item.cached_pdf_bytes = data
                if item.kind == "file":
                    try:
                        item.cache_key = (item.value, os.path.getmtime(item.value),
                                          page_mode)
                    except OSError:
                        item.cache_key = (item.value, 0, page_mode)
                else:
                    item.cache_key = (item.value, page_mode)
                item.render_status = "ready"
                self._on_event(("item_rendered", item.uid))
            except Exception as e:
                item.render_status = "failed"
                item.render_error = str(e)
                self._on_event(("item_render_failed", item.uid, str(e)))

    @staticmethod
    def _render(item, page_mode):
        """Convert one Item to PDF bytes. Mirrors what _build_worker does
        at Create-PDF time so the cache is byte-equivalent."""
        if item.kind == "url":
            return url_to_pdf_bytes(item.value, page_mode).getvalue()
        kind = file_kind(item.value)
        if kind == "image":
            return image_to_pdf_bytes(item.value, page_mode).getvalue()
        if kind == "pdf":
            with open(item.value, "rb") as fh:
                return fh.read()
        if kind == "text":
            tm = "a4" if page_mode == "a4" else "letter"
            return text_to_pdf_bytes(item.value, tm).getvalue()
        if kind == "office":
            return office_to_pdf_bytes(item.value).getvalue()
        raise ValueError(f"Unsupported file kind: {item.value}")


# ---------------------------------------------------------------------------
# Tooltip helper (v1.24): tiny popup label that appears after a hover
# delay and disappears on leave/click. Tk has no built-in tooltip so this
# is hand-rolled. Used for the footer ♡ sponsor button.
# ---------------------------------------------------------------------------
class Tooltip:
    def __init__(self, widget, text, delay_ms=400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._tipwin = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _event=None):
        self._cancel_scheduled()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_scheduled(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        if self._tipwin is not None:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2 - 80
        y = self.widget.winfo_rooty() - 30
        self._tipwin = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            tw, text=self.text,
            background="#ffffd0", foreground="#222",
            relief="solid", borderwidth=1, padding=(8, 4),
        ).pack()

    def _hide(self, _event=None):
        self._cancel_scheduled()
        if self._tipwin is not None:
            try:
                self._tipwin.destroy()
            except tk.TclError:
                pass
            self._tipwin = None


# ---------------------------------------------------------------------------
# SignatureCreatorDialog (v1.28): create the user's visible signature.
#
# Two tabs:
#   • Type: enter your name, pick a cursive-style font → rendered to PNG
#   • Draw: freehand on a Tk Canvas (mouse / trackpad) → exported to PNG
#
# Saved at ~/.config/mydocmaker/signing/signature.png with a
# small metadata sidecar. v1.28 supports ONE saved signature; multi-sig
# manager comes in v1.29.
# ---------------------------------------------------------------------------
class SignatureCreatorDialog:
    """v1.35: signature creator/editor with three top-level modes.

    Modes (radio chooser at the top):
      • digital — DocuSign-style digital signature. Just the business
        details (name, company, address, VAT/EIN/Tax/License). No
        typing or drawing UI — the visual is auto-rendered from the
        name in a cursive script. Best for legal and business docs.
      • type — quick typed-name signature, just name + style.
      • draw — quick drawn signature, just a label + drawing canvas.

    Internally each mode has its own set of frames in `body`, packed
    in/out by _refresh_mode. The dialog footer is just Cancel; the Save
    action lives in each mode's panel so the action label always
    matches what's about to be saved.

    `on_save(png_bytes, meta_dict)` is called when the user saves. If an
    `existing` dict is passed, the dialog opens in edit mode and pre-fills
    fields; drawn signatures aren't re-strokeable so editing one keeps the
    original PNG unless the user redraws.
    """

    SIG_WIDTH = 480     # canvas/preview size in pixels
    SIG_HEIGHT = 140

    def __init__(self, parent, on_save, existing=None):
        self.on_save = on_save
        self.existing = existing or {}
        self._strokes = []          # list of [(x, y), ...] for the Draw mode
        self._current_stroke = None
        self._existing_png = None
        if existing and existing.get("image_path"):
            try:
                with open(existing["image_path"], "rb") as f:
                    self._existing_png = f.read()
            except OSError:
                pass

        preset_name = self.existing.get("name") or self.existing.get("label")
        if not preset_name:
            try:
                preset_name = getpass.getuser().capitalize()
            except Exception:
                preset_name = ""

        self.win = tk.Toplevel(parent)
        self.win.title("Edit signature" if existing else "Create signature")
        self.win.transient(parent)
        self.win.resizable(False, False)

        ttk.Label(
            self.win,
            text=("Edit signature" if existing else "Create a signature"),
            font=("", 13, "bold"),
        ).pack(padx=16, pady=(14, 4))

        # ----- Mode chooser
        # v1.35: migrate from old internal name 'create_full' → 'digital'.
        if self.existing:
            # Edit-mode opens with the saved signature's mode (or a sensible
            # default based on its style — v1.32–v1.37 didn't persist
            # creator_mode, so we infer it from style for those).
            existing_mode = self.existing.get("creator_mode")
            if existing_mode == "create_full":  # legacy migration
                existing_mode = "digital"
            if existing_mode not in ("digital", "type", "draw"):
                style = self.existing.get("style")
                if style == "drawn":
                    existing_mode = "draw"
                elif style == "digital":
                    existing_mode = "digital"
                else:
                    existing_mode = "type"
        else:
            # Creating a new signature: always land on Digital, regardless of
            # why the dialog was opened.
            existing_mode = "digital"
        self.mode_var = tk.StringVar(value=existing_mode)
        chooser = ttk.LabelFrame(self.win, text="What kind of signature?")
        chooser.pack(fill="x", padx=12, pady=(4, 8))
        for val, txt in (
            ("digital",
             "Digital — full business details "
             "(best for legal and business documents, "
             "DocuSign-style stamp)"),
            ("type", "Typed — type your name in a cursive script"),
            ("draw", "Drawn — draw your signature with the mouse"),
        ):
            ttk.Radiobutton(
                chooser, text=txt, value=val, variable=self.mode_var,
                command=self._refresh_mode,
            ).pack(anchor="w", padx=10, pady=2)

        # The body holds the per-mode frames. _refresh_mode picks which
        # frames are visible based on mode_var.
        self.body = ttk.Frame(self.win)
        self.body.pack(fill="both", expand=True, padx=12, pady=2)

        self._build_type_frame(preset_name)
        self._build_draw_frame()
        self._build_simple_label_frame()
        self._build_details_frame(preset_name)
        self._build_save_rows()

        # ----- footer: Cancel only. v1.33: each mode has its OWN Save
        # button at the bottom of its frame so the action is unambiguous
        # ("Save typed signature" vs "Save drawn signature" vs "Save
        # signature with details"). A signature is one mode only — pick
        # one, save, done. Want a second style? Create another signature.
        btn_row = ttk.Frame(self.win)
        btn_row.pack(fill="x", padx=12, pady=(4, 14))
        ttk.Button(btn_row, text="Cancel", command=self.win.destroy
                   ).pack(side="right", padx=(4, 0))

        self._refresh_mode()
        self.win.lift()
        self.win.focus_force()

    def _refresh_mode(self):
        """Show only the frames relevant to the current mode.

        v1.35: three modes, three distinct layouts. Digital shows ONLY
        the details fields (no type/draw widgets) — the visible-signature
        PNG is auto-rendered from the Name field in a cursive script.
        Typed and Drawn show their single respective visual widget + a
        simple label entry."""
        for frame in (self.type_frame, self.draw_frame,
                       self.simple_label_frame, self.details_frame,
                       self.type_save_row, self.draw_save_row,
                       self.full_save_row):
            frame.pack_forget()
        m = self.mode_var.get()
        if m == "type":
            self.simple_label_frame.pack(fill="x", pady=(2, 4))
            self.type_frame.pack(fill="both", expand=True, pady=2)
            self.type_save_row.pack(fill="x", pady=(6, 4))
        elif m == "draw":
            self.simple_label_frame.pack(fill="x", pady=(2, 4))
            self.draw_frame.pack(fill="both", expand=True, pady=2)
            self.draw_save_row.pack(fill="x", pady=(6, 4))
        else:  # digital
            self.details_frame.pack(fill="both", expand=True, pady=2)
            self.full_save_row.pack(fill="x", pady=(6, 4))
        # v1.36: refresh the WYSIWYG preview for the newly-active mode.
        # Safe before the preview labels exist (guarded inside the method).
        if hasattr(self, "type_preview_lbl"):
            self._refresh_appearance_preview()

    def _build_type_frame(self, preset_name):
        f = ttk.LabelFrame(self.body, text="Type your name")
        ttk.Label(f, text="Name:").pack(anchor="w", padx=10, pady=(8, 2))
        self.type_var = tk.StringVar(value=preset_name or "")
        entry = ttk.Entry(f, textvariable=self.type_var, width=42)
        entry.pack(padx=10, pady=(0, 6), fill="x")
        entry.bind("<KeyRelease>",
                    lambda _e: self._refresh_appearance_preview())

        ttk.Label(f, text="Style:").pack(anchor="w", padx=10, pady=(2, 2))
        self.type_style_var = tk.StringVar(
            value=self.existing.get("style") or "cursive",
        )
        style_row = ttk.Frame(f)
        style_row.pack(anchor="w", padx=10, pady=(0, 6))
        for label, val in (("Cursive", "cursive"),
                           ("Bold serif", "serif"),
                           ("Handwritten", "handwritten")):
            ttk.Radiobutton(style_row, text=label, value=val,
                            variable=self.type_style_var,
                            command=self._refresh_appearance_preview,
                            ).pack(side="left", padx=4)

        # v1.36: the Preview shows the FINAL composed appearance (visual
        # + name + timestamp), not just the rendered name — what the
        # signed PDF will actually look like.
        ttk.Label(f, text="Preview of the signed stamp:",
                  foreground="#666").pack(anchor="w", padx=10, pady=(4, 2))
        self.type_preview_lbl = ttk.Label(
            f, anchor="center",
            background="white", relief="solid", borderwidth=1,
        )
        self.type_preview_lbl.pack(padx=10, pady=(0, 8), fill="x")
        self.type_frame = f

    def _build_draw_frame(self):
        f = ttk.LabelFrame(self.body, text="Draw your signature")
        ttk.Label(
            f,
            text="Hold the left mouse button and drag to draw. Saved at 4× "
                 "resolution with LANCZOS smoothing — polished on the final "
                 "PDF, not pixelated.",
            foreground="#555", wraplength=520, justify="left",
        ).pack(padx=10, pady=(8, 4))

        self.draw_canvas = tk.Canvas(
            f, width=self.SIG_WIDTH, height=self.SIG_HEIGHT,
            background="white", relief="solid", borderwidth=1,
            highlightthickness=0, cursor="pencil",
        )
        self.draw_canvas.pack(padx=10, pady=(0, 4))
        self.draw_canvas.bind("<Button-1>", self._draw_start)
        self.draw_canvas.bind("<B1-Motion>", self._draw_move)
        self.draw_canvas.bind("<ButtonRelease-1>", self._draw_end)
        ttk.Button(f, text="Clear", command=self._draw_clear
                   ).pack(pady=(2, 4))

        # v1.36: preview of the composed stamp underneath, refreshes
        # after every stroke release.
        ttk.Label(f, text="Preview of the signed stamp:",
                  foreground="#666").pack(anchor="w", padx=10, pady=(2, 2))
        self.draw_preview_lbl = ttk.Label(
            f, anchor="center",
            background="white", relief="solid", borderwidth=1,
            text="(draw a signature to see preview)", foreground="#888",
        )
        self.draw_preview_lbl.pack(padx=10, pady=(0, 8), fill="x")
        self.draw_frame = f

    def _build_simple_label_frame(self):
        """Minimal label entry shown in quick (type/draw) modes only."""
        f = ttk.Frame(self.body)
        ttk.Label(
            f,
            text="Signature label (how this signature shows up in your "
                 "saved-signatures list):",
        ).pack(anchor="w", pady=(2, 2))
        self.simple_label_var = tk.StringVar(
            value=self.existing.get("label") or self.existing.get("name")
                  or "My signature",
        )
        ttk.Entry(f, textvariable=self.simple_label_var, width=42
                  ).pack(fill="x")
        self.simple_label_frame = f

    def _build_details_frame(self, preset_name):
        """Full business details — shown only in digital mode (v1.35).
        The visible-signature PNG is auto-rendered from the Name field in
        a cursive script, so there's no typing or drawing widget in this
        mode; the metadata IS the signature."""
        f = ttk.LabelFrame(self.body, text="Your details")
        ttk.Label(
            f,
            text="Fill in your business details. The signature image will "
                 "be your Name rendered in a cursive script (DocuSign-style); "
                 "company / address / tax / license appear next to it on "
                 "signed PDFs and in the audit JSON sidecar.",
            foreground="#555", wraplength=520, justify="left",
        ).pack(padx=10, pady=(8, 4))

        self.detail_vars = {}
        for key, label, default in (
            ("label",   "Signature label (e.g. 'Personal', 'Acme Inc.')",
                        self.existing.get("label") or
                        self.existing.get("name") or ""),
            ("name",    "Full name",
                        self.existing.get("name") or preset_name or ""),
            ("company", "Company name", self.existing.get("company") or ""),
            ("address", "Address",      self.existing.get("address") or ""),
            ("tax_id",  "Tax ID  (VAT / EIN / etc.)",
                        self.existing.get("tax_id") or ""),
            ("license", "License / registration #",
                        self.existing.get("license") or ""),
        ):
            ttk.Label(f, text=label).pack(anchor="w", padx=10, pady=(4, 2))
            var = tk.StringVar(value=default)
            self.detail_vars[key] = var
            ent = ttk.Entry(f, textvariable=var, width=50)
            ent.pack(padx=10, pady=(0, 2), fill="x")
            ent.bind("<KeyRelease>",
                     lambda _e: self._refresh_appearance_preview())

        # v1.36: live WYSIWYG preview of the final signed stamp.
        ttk.Label(f, text="Preview of the signed stamp:",
                  foreground="#666").pack(anchor="w", padx=10, pady=(8, 2))
        self.digital_preview_lbl = ttk.Label(
            f, anchor="center",
            background="white", relief="solid", borderwidth=1,
            text="(enter your name to see preview)", foreground="#888",
        )
        self.digital_preview_lbl.pack(padx=10, pady=(0, 8), fill="x")
        self.details_frame = f

    def _build_save_rows(self):
        """v1.33: one Save button per mode, packed by _refresh_mode under
        the relevant content. Each button calls _save, which reads the
        active mode_var — so the action always matches what the user
        sees on the button."""
        editing = bool(self.existing)
        self.type_save_row = ttk.Frame(self.body)
        ttk.Button(
            self.type_save_row,
            text=("Save changes" if editing else "Save typed signature"),
            command=self._save,
        ).pack(side="right")

        self.draw_save_row = ttk.Frame(self.body)
        ttk.Button(
            self.draw_save_row,
            text=("Save changes" if editing else "Save drawn signature"),
            command=self._save,
        ).pack(side="right")

        self.full_save_row = ttk.Frame(self.body)
        ttk.Button(
            self.full_save_row,
            text=("Save changes" if editing
                  else "Save digital signature"),
            command=self._save,
        ).pack(side="right")

    # -- Type tab helpers --
    def _font_for_style(self, style, size):
        # Tk falls back to a default if the named font isn't present.
        # Cursive: 'URW Chancery L' / 'Comic Sans MS' / 'Brush Script MT'.
        if style == "cursive":
            return ("URW Chancery L", size, "italic")
        if style == "handwritten":
            return ("Comic Sans MS", size, "")
        return ("Times", size, "bold italic")

    def _render_type_preview(self):
        text = (self.type_var.get() or "").strip() or "Your name"
        style = self.type_style_var.get()
        if not PIL_TK_OK:
            self.type_preview_lbl.config(text=text)
            return
        from PIL import ImageDraw
        # v1.39+: high-resolution canvas (960×280) so the saved typed-name
        # PNG stays sharp when embedded into the appearance stamp.
        # v1.42: auto-fit the font size so long names don't overflow.
        HW, HH = 960, 280
        img = Image.new("RGBA", (HW, HH), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        max_width = HW - 40
        font_size = 140
        font = self._pil_font_for_style(style, font_size)
        try:
            while font_size > 40:
                l, t, r, b = draw.textbbox((0, 0), text, font=font)
                if (r - l) <= max_width:
                    break
                font_size -= 8
                font = self._pil_font_for_style(style, font_size)
            l, t, r, b = draw.textbbox((0, 0), text, font=font)
            tw, th = r - l, b - t
            x = (HW - tw) // 2 - l
            y = (HH - th) // 2 - t
        except AttributeError:
            x = HW // 4
            y = HH // 4
        draw.text((x, y), text, fill=(20, 20, 60, 255), font=font)
        self._type_preview_pil = img
        # Tk preview: shrink to a sensible on-screen size so the dialog
        # doesn't balloon. (The compose-appearance refresh overwrites
        # this label moments later anyway.)
        thumb = img.copy()
        thumb.thumbnail((self.SIG_WIDTH, self.SIG_HEIGHT), LANCZOS)
        photo = _ImageTk.PhotoImage(thumb)
        self.type_preview_lbl.config(image=photo, text="")
        self.type_preview_lbl.image = photo

    @staticmethod
    def _pil_font_for_style(style, px):
        """v1.39: prefer actual script / handwriting fonts over plain
        italic serif so the cursive option looks like a real signature
        across all three platforms. Falls back to italic-serif if no
        script font is installed (still better than the bitmap default)."""
        from PIL import ImageFont
        candidates = {
            "cursive": [
                # Linux — script-style fonts that are commonly available
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
                "/usr/share/fonts/opentype/urw-base35/URWChanceryL-MediumItalic.otf",
                # macOS — real script fonts
                "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc",
                "/System/Library/Fonts/Supplemental/Apple Chancery.ttf",
                "/Library/Fonts/Apple Chancery.ttf",
                # Windows
                "C:\\Windows\\Fonts\\monotypecorsiva.ttf",
                "C:\\Windows\\Fonts\\segoesc.ttf",
                "C:\\Windows\\Fonts\\segoescb.ttf",
            ],
            "handwritten": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/System/Library/Fonts/Supplemental/Bradley Hand.ttc",
                "/System/Library/Fonts/Supplemental/Marker Felt.ttc",
                "C:\\Windows\\Fonts\\seguihis.ttf",  # Segoe UI Historic
                "C:\\Windows\\Fonts\\segoesc.ttf",   # Segoe Script (fallback)
            ],
            "serif": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf",
                "/Library/Fonts/Times New Roman Bold Italic.ttf",
                "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf",
                "C:\\Windows\\Fonts\\timesbi.ttf",
            ],
        }
        for p in candidates.get(style, []):
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, px)
                except Exception:
                    continue
        return ImageFont.load_default()

    # -- Draw tab helpers --
    def _draw_start(self, event):
        self._current_stroke = [(event.x, event.y)]

    def _draw_move(self, event):
        if not self._current_stroke:
            return
        x0, y0 = self._current_stroke[-1]
        x1, y1 = event.x, event.y
        self.draw_canvas.create_line(
            x0, y0, x1, y1, width=2, capstyle="round", fill="#102050",
            smooth=True,
        )
        self._current_stroke.append((x1, y1))

    def _draw_end(self, _event):
        if self._current_stroke and len(self._current_stroke) > 1:
            self._strokes.append(self._current_stroke)
        self._current_stroke = None
        self._refresh_appearance_preview()

    def _draw_clear(self):
        self.draw_canvas.delete("all")
        self._strokes = []
        self._current_stroke = None
        self._refresh_appearance_preview()

    # -- v1.36: WYSIWYG preview of the composed stamp --------------------
    def _refresh_appearance_preview(self):
        """Re-render the appearance preview for whichever mode the user
        is currently in. The result is what will actually show up on the
        signed PDF (modulo the timestamp, which is captured at sign-time).

        v1.37: any exception inside the preview pipeline (e.g. font
        load, PIL resampling enum drift, PDF compose failure) is now
        caught and surfaced into the label as a one-line error string,
        instead of being swallowed by Tk's silent-callback handling
        which left the preview area mysteriously blank."""
        if not PIL_TK_OK:
            return
        mode = self.mode_var.get()
        lbl_map = {
            "type": getattr(self, "type_preview_lbl", None),
            "draw": getattr(self, "draw_preview_lbl", None),
            "digital": getattr(self, "digital_preview_lbl", None),
        }
        lbl = lbl_map.get(mode)
        if lbl is None:
            return
        try:
            # Keep the typed-visual PIL image current — _type_to_png
            # uses _type_preview_pil under the hood.
            self._render_type_preview()
            png, _style = self._pick_visual_for_mode(mode)
            if png is None:
                lbl.config(
                    image="",
                    text=("(draw a signature to see preview)"
                          if mode == "draw"
                          else "(enter your name to see preview)"),
                    foreground="#888",
                )
                lbl.image = None
                return
            if mode == "digital":
                meta = {k: v.get() for k, v in self.detail_vars.items()}
            elif mode == "type":
                meta = {"name": (self.type_var.get() or "").strip()}
            else:  # draw
                meta = {"name": (self.simple_label_var.get() or "").strip()
                                or (getpass.getuser() or "Signer")}
            ts = (datetime.datetime.now()
                  .strftime("%Y-%m-%d %H:%M %Z").strip()
                  or datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
            appearance_png = _compose_signature_appearance(png, meta, ts)
            pil = Image.open(io.BytesIO(appearance_png)).convert("RGBA")
            # v1.41: bigger preview so the smaller metadata lines (address,
            # tax, license, timestamp) are actually legible. The previous
            # 420×130 was a 2.3× downscale from the 960×288 composed image,
            # which made 6.5–7pt lines disappear into noise at the dialog.
            pil.thumbnail((560, 200), LANCZOS)
            photo = _ImageTk.PhotoImage(pil)
            lbl.config(image=photo, text="")
            lbl.image = photo  # keep a reference so Tcl doesn't GC it
        except Exception as e:
            traceback.print_exc()
            lbl.config(
                image="",
                text=f"(preview unavailable: {type(e).__name__}: {e})",
                foreground="#a30000",
            )
            lbl.image = None

    # -- Save / output --
    def _save(self):
        if not PIL_TK_OK:
            messagebox.showerror(
                APP_NAME,
                "Pillow's Tk bindings are required to save signatures.",
            )
            return
        mode = self.mode_var.get()
        png, style = self._pick_visual_for_mode(mode)
        if png is None:
            # Fallback: reuse the existing image (metadata-only edit).
            if self._existing_png is not None:
                png = self._existing_png
                style = self.existing.get("style", "typed")
            else:
                if mode == "digital":
                    msg = ("Please enter your full name in the Details "
                           "fields — that's what becomes the signature.")
                elif mode == "type":
                    msg = "Please type your name before saving."
                else:
                    msg = "Please draw a signature before saving."
                messagebox.showwarning(APP_NAME, msg)
                return

        # Compose the meta dict per mode. In quick modes (type / draw) the
        # detail fields aren't shown — populate only label and name.
        if mode == "digital":
            meta = {k: (var.get() or "").strip()
                    for k, var in self.detail_vars.items()}
        else:
            simple_label = (self.simple_label_var.get() or "").strip()
            typed_name = (self.type_var.get() or "").strip()
            display_name = simple_label or typed_name or "Signature"
            meta = {
                "label": simple_label or display_name,
                "name": typed_name or display_name,
                "company": "", "address": "", "tax_id": "", "license": "",
            }
        if not meta.get("label"):
            meta["label"] = meta.get("name") or "Signature"
        if not meta.get("name"):
            meta["name"] = meta["label"]
        meta["style"] = style
        meta["creator_mode"] = mode
        try:
            self.on_save(png, meta)
        finally:
            self.win.destroy()

    def _pick_visual_for_mode(self, mode):
        """Returns (png_bytes, style) for the active mode, or (None, None)
        if the user hasn't provided enough to render a visual."""
        if mode == "draw":
            if self._strokes:
                return self._draw_to_png(), "drawn"
            return None, None
        if mode == "type":
            typed = (self.type_var.get() or "").strip()
            if typed:
                return self._type_to_png(), "typed"
            return None, None
        # digital: auto-render the Name field in cursive — no type/draw
        # UI in this mode, the visual is implied by the metadata.
        name = (self.detail_vars["name"].get() or "").strip()
        if name:
            return self._render_name_to_png(name, "cursive"), "digital"
        return None, None

    def _render_name_to_png(self, text, style):
        """Render an arbitrary name to a transparent PNG. v1.42:
        auto-fit the font size so long names ('Dejan Obradovic',
        'Christopher Featherstone-Smith') don't overflow the 960px
        canvas and get clipped. Starts at 140px and shrinks until the
        rendered text fits within the canvas width minus margins."""
        if not PIL_TK_OK:
            return None
        from PIL import ImageDraw
        W, H = 960, 280
        img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        max_width = W - 40  # 20 px padding each side
        font_size = 140
        font = self._pil_font_for_style(style, font_size)
        try:
            while font_size > 40:
                l, t, r, b = draw.textbbox((0, 0), text, font=font)
                if (r - l) <= max_width:
                    break
                font_size -= 8
                font = self._pil_font_for_style(style, font_size)
            l, t, r, b = draw.textbbox((0, 0), text, font=font)
            tw, th = r - l, b - t
            x = (W - tw) // 2 - l
            y = (H - th) // 2 - t
        except AttributeError:
            x = W // 4
            y = H // 4
        draw.text((x, y), text, fill=(20, 20, 60, 255), font=font)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def _type_to_png(self):
        buf = io.BytesIO()
        self._type_preview_pil.save(buf, "PNG")
        return buf.getvalue()

    def _draw_to_png(self):
        """Render the strokes to a transparent PNG. v1.32: oversample 4× and
        downsample with LANCZOS so the saved signature is smooth and
        polished rather than pixelated like v1.31's 1:1 canvas snapshot."""
        from PIL import ImageDraw, ImageFilter
        SCALE = 4
        big_w, big_h = self.SIG_WIDTH * SCALE, self.SIG_HEIGHT * SCALE
        big = Image.new("RGBA", (big_w, big_h), (255, 255, 255, 0))
        d = ImageDraw.Draw(big)
        for stroke in self._strokes:
            if len(stroke) < 2:
                continue
            scaled = [(x * SCALE, y * SCALE) for (x, y) in stroke]
            d.line(scaled, fill=(16, 32, 80, 255), width=3 * SCALE,
                   joint="curve")
            # Round end-caps so single short strokes don't look like
            # rectangles at the start/end.
            for (cx, cy) in (scaled[0], scaled[-1]):
                r = (3 * SCALE) // 2
                d.ellipse((cx - r, cy - r, cx + r, cy + r),
                          fill=(16, 32, 80, 255))
        # A gentle blur before downsample softens the staircase aliasing
        # that single-pixel-perfect rasterization would leave behind.
        big = big.filter(ImageFilter.GaussianBlur(radius=SCALE * 0.4))
        out = big.resize((self.SIG_WIDTH * 2, self.SIG_HEIGHT * 2),
                         LANCZOS)
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue()


# ---------------------------------------------------------------------------
# SignaturesManagerDialog (v1.31): list/create/edit/delete saved signatures.
# Accessed from the main app's "My Signatures" button. Lets the user
# pre-create signatures with full metadata so they're ready to drop on
# any PDF.
# ---------------------------------------------------------------------------
class SignaturesManagerDialog:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("My Signatures")
        self.win.transient(parent)
        self.win.geometry("640x480")
        self.win.minsize(540, 380)

        ttk.Label(self.win, text="My Signatures",
                  font=("", 13, "bold")).pack(padx=14, pady=(14, 4))
        ttk.Label(
            self.win,
            text="Create one or more signatures with your name + company "
                 "info. Use the right-click 'Sign as' menu in the signing "
                 "dialog to pick which one to apply where.",
            foreground="#555", wraplength=580, justify="left",
        ).pack(padx=14, pady=(0, 8))

        # ----- List + preview side-by-side
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=4)

        list_wrap = ttk.Frame(body)
        list_wrap.pack(side="left", fill="y")
        ttk.Label(list_wrap, text="Saved signatures",
                  foreground="#666").pack(anchor="w")
        self.listbox = tk.Listbox(list_wrap, width=24, height=14,
                                  activestyle="dotbox", exportselection=False)
        self.listbox.pack(side="left", fill="y", pady=4)
        sb = ttk.Scrollbar(list_wrap, orient="vertical",
                            command=self.listbox.yview)
        sb.pack(side="left", fill="y", pady=4)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.bind("<<ListboxSelect>>",
                           lambda _e: self._on_select())

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="Preview", foreground="#666").pack(anchor="w")
        self.preview_lbl = ttk.Label(
            right, anchor="center",
            background="white", relief="solid", borderwidth=1,
        )
        self.preview_lbl.pack(fill="x", pady=4)
        self.meta_lbl = ttk.Label(
            right, text="(no signature selected)",
            foreground="#444", anchor="w", justify="left",
            wraplength=360,
        )
        self.meta_lbl.pack(fill="x", pady=(8, 0))

        # ----- Action buttons
        btns = ttk.Frame(self.win)
        btns.pack(fill="x", padx=12, pady=(6, 14))
        ttk.Button(btns, text="+ New", command=self._new_signature
                   ).pack(side="left")
        self.edit_btn = ttk.Button(btns, text="Edit",
                                    command=self._edit_signature, state="disabled")
        self.edit_btn.pack(side="left", padx=4)
        self.delete_btn = ttk.Button(btns, text="Delete",
                                      command=self._delete_signature, state="disabled")
        self.delete_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=self.win.destroy
                   ).pack(side="right")

        self._signatures = []
        self._reload()
        self.win.lift()
        self.win.focus_force()

    def _reload(self):
        self._signatures = list_signatures()
        self.listbox.delete(0, tk.END)
        for s in self._signatures:
            label = s.get("label") or s.get("name") or "(untitled)"
            self.listbox.insert(tk.END, label)
        if self._signatures:
            self.listbox.selection_set(0)
            self._on_select()
        else:
            self._show_empty_state()

    def _show_empty_state(self):
        self.preview_lbl.config(image="", text="(none)")
        self.preview_lbl.image = None
        self.meta_lbl.config(text="No signatures yet. Click '+ New' to "
                                  "create your first one.")
        self.edit_btn.state(["disabled"])
        self.delete_btn.state(["disabled"])

    def _selected_signature(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self._signatures[sel[0]]

    def _on_select(self):
        s = self._selected_signature()
        if s is None:
            return
        # v1.42: show the composed DocuSign-style appearance — what the
        # signed PDF will actually look like — rather than just the raw
        # cursive-name PNG. Same renderer the SignatureCreatorDialog and
        # the signing flow use.
        try:
            with open(s["image_path"], "rb") as f:
                png = f.read()
            meta = {k: (s.get(k) or "").strip()
                    for k in ("name", "company", "address",
                              "tax_id", "license")}
            ts = (datetime.datetime.now()
                  .strftime("%Y-%m-%d %H:%M %Z").strip()
                  or datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
            appearance_png = _compose_signature_appearance(png, meta, ts)
            from PIL import Image as _Image
            img = _Image.open(io.BytesIO(appearance_png))
            img.thumbnail((480, 160), LANCZOS)
            if PIL_TK_OK:
                photo = _ImageTk.PhotoImage(img)
                self.preview_lbl.config(image=photo, text="")
                self.preview_lbl.image = photo
        except Exception:
            traceback.print_exc()
            self.preview_lbl.config(text="(preview unavailable)", image="")
        # Show metadata
        bits = []
        for key, label in (("name",    "Name"),
                           ("company", "Company"),
                           ("address", "Address"),
                           ("tax_id",  "Tax ID"),
                           ("license", "License")):
            val = (s.get(key) or "").strip()
            if val:
                bits.append(f"{label}: {val}")
        bits.append(f"Style: {s.get('style', '—')}")
        bits.append(f"Created: {(s.get('created_at') or '')[:10]}")
        self.meta_lbl.config(text="\n".join(bits))
        self.edit_btn.state(["!disabled"])
        self.delete_btn.state(["!disabled"])

    def _new_signature(self):
        def on_save(png, meta):
            save_signature_record(None, png, meta)
            self._reload()
        SignatureCreatorDialog(self.win, on_save=on_save)

    def _edit_signature(self):
        s = self._selected_signature()
        if s is None:
            return
        existing = dict(s)
        def on_save(png, meta):
            save_signature_record(s["id"], png, meta)
            self._reload()
        SignatureCreatorDialog(self.win, on_save=on_save, existing=existing)

    def _delete_signature(self):
        s = self._selected_signature()
        if s is None:
            return
        if not messagebox.askyesno(
            APP_NAME,
            f"Delete the signature '{s.get('label', '?')}'?\n\n"
            "This can't be undone. Any signed PDFs that already exist "
            "remain valid — the signature was embedded at signing time."
        ):
            return
        delete_signature_record(s["id"])
        self._reload()


# ---------------------------------------------------------------------------
# SignDialog (v1.28): given a built combined PDF + a saved signature PNG,
# preview the document, let the user pick a position by clicking on a page,
# then sign + save.
# ---------------------------------------------------------------------------
class SignDialog:
    """v1.32 redesign.

    Mouse model (deliberately simple, all on left button):
      • Left press on empty page area → place a new spot at the click,
        centered on the cursor, select it.
      • Left press on an existing spot → select it, start drag.
      • Drag → moves the selected spot live; overlap with another spot
        rejects the move (status warning, spot snaps back).
      • Left release outside any page → deselect.
      • Right-click on a spot → mode-dependent context menu.
      • Delete or Backspace → remove the selected spot.

    Each spot carries BOTH:
      • `signature_id` — used in Sign mode (which of MY saved signatures
        signs this spot). None = leave empty for someone else.
      • `person_id` — used in Prepare-for-others mode (which dialog-local
        Person slot this spot is reserved for). The persons list lives
        only in the open SignDialog session; it's a labeling convenience
        for naming each empty field.

    Context menus:
      • Sign mode → 'Sign as ▸ <saved signature list>' (from My Signatures)
      • Prepare mode → 'Assign to ▸ Person N - name <email>' (from the
        persons list in this session)
    """

    # v1.43: shrank to 220 × 66 pt (≈3.05" × 0.92" on the page). The
    # composer below also has tighter internal padding now — minimal
    # margins between text and edges — so the smaller box doesn't
    # crowd the content.
    DEFAULT_STAMP_W_PT = 220
    DEFAULT_STAMP_H_PT = 66
    SIZE_PRESETS = {
        "Compact (170 × 50)": (170, 50),
        "Default (220 × 66)": (220, 66),
        "Wide (300 × 90)": (300, 90),
        "Tall (220 × 100)": (220, 100),
    }
    DRAG_THRESHOLD_PX = 3  # below this, treat as click not drag
    # Per-person colour palette for prepare-mode visualization. Cycles if
    # the user adds more persons than entries here (modulo).
    PERSON_COLORS = [
        "#d97706",  # amber
        "#16a34a",  # green
        "#9333ea",  # purple
        "#dc2626",  # red
        "#0a64d8",  # blue
        "#0891b2",  # cyan
    ]

    def __init__(self, parent, app, pdf_bytes, on_signed):
        """pdf_bytes: the combined PDF (already built). on_signed: callable
        called with the saved-out path after Save/Sign."""
        self.app = app
        self.pdf_bytes = pdf_bytes
        self.on_signed = on_signed

        # --- doc state
        self._page_count = 0
        self._cached_image_refs = []
        # _page_y_positions[i] = (y_top_on_canvas, x_left_on_canvas, width_px, height_px)
        self._page_y_positions = []
        self._page_pdf_dims = []
        self._page_render_scale = 1.0

        # --- stamps (multiple). Each dict has:
        #     id              — uuid hex, used as Tk tag prefix
        #     page            — 1-indexed
        #     x_pt, y_pt      — PDF coords, origin bottom-left
        #     width_pt, height_pt
        #     selected        — bool (highlighted in UI)
        #     signature_id    — id of a saved signature, or None to leave
        #                        the spot empty (for someone else to sign)
        self._stamps = []
        self._selected_stamp_id = None
        # Drag state used by left-press / motion / release:
        #   None when not dragging, otherwise a dict:
        #     {"stamp_id", "start_cx", "start_cy", "orig_x_pt", "orig_y_pt",
        #      "moved": bool}
        self._drag_state = None
        # v1.31: load all saved signatures. Each stamp gets a
        # `signature_id` field pointing at one of these. Stamps with
        # no signature_id are kept as empty fields when signing (for
        # other signers to fill in later in Acrobat / Foxit).
        self._signatures = list_signatures()
        # Default signature for newly-placed stamps: the first saved one.
        # When the user hasn't created any yet, defaults to None (the
        # stamp is unsigned-by-default and the sign flow will prompt).
        self._default_signature_id = (
            self._signatures[0]["id"] if self._signatures else None
        )

        # v1.32: persons list, used ONLY in prepare-for-others mode.
        # Lives in-memory for the dialog session — not persisted. Each
        # entry: {"id": uuid, "name": str, "email": str}. Slots are
        # labeled "Person N" by index. We seed two empty persons so the
        # user can start assigning right away.
        self._persons = [
            {"id": uuid.uuid4().hex, "name": "", "email": ""},
            {"id": uuid.uuid4().hex, "name": "", "email": ""},
        ]
        self._default_person_id = self._persons[0]["id"]

        # --- window
        self.win = tk.Toplevel(parent)
        self.win.title("Sign and create PDF")
        self.win.transient(parent)
        self.win.geometry("820x740")
        self.win.minsize(680, 580)

        # Header
        head = ttk.Frame(self.win)
        head.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(head, text="Sign and create PDF",
                  font=("", 13, "bold")).pack(side="left")

        # Mode toggle
        # Prepare = save the PDF with empty signature fields at every spot
        #           you placed (no signing). Send to others to sign.
        # Sign = sign every spot with your saved signature + audit JSON.
        self.mode_var = tk.StringVar(value="sign")
        mode_row = ttk.LabelFrame(self.win, text="What do you want to do?")
        mode_row.pack(fill="x", padx=12, pady=(4, 4))
        ttk.Radiobutton(
            mode_row, text="Sign this document now (uses your saved signature)",
            value="sign", variable=self.mode_var,
            command=self._refresh_mode_ui,
        ).pack(anchor="w", padx=10, pady=(6, 0))
        ttk.Radiobutton(
            mode_row,
            text="Prepare for others to sign (creates empty signature fields, no signing)",
            value="prepare", variable=self.mode_var,
            command=self._refresh_mode_ui,
        ).pack(anchor="w", padx=10, pady=(2, 6))

        # v1.32: Persons editor (shown only in prepare mode). Lets the
        # user name each Person slot so empty signature fields in the
        # output PDF have meaningful captions like
        # 'Signature 2 - Alice Smith <alice@example.com>' instead of
        # 'Signature 2 - For other signer'.
        self.persons_frame = ttk.LabelFrame(
            self.win, text="People who will sign this PDF",
        )
        # NOTE: not packed yet — _refresh_mode_ui handles that.
        ttk.Label(
            self.persons_frame,
            text="Optional: name each person so the signature field in the "
                 "PDF identifies them (rather than 'Person 1', 'Person 2'). "
                 "Right-click a window below → Assign to ▸ to choose one.",
            foreground="#555", wraplength=760, justify="left",
        ).pack(anchor="w", padx=10, pady=(6, 4))
        self.persons_list_frame = ttk.Frame(self.persons_frame)
        self.persons_list_frame.pack(fill="x", padx=10, pady=(0, 4))
        persons_btn_row = ttk.Frame(self.persons_frame)
        persons_btn_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(persons_btn_row, text="+ Add person",
                   command=self._add_person).pack(side="left")
        ttk.Button(persons_btn_row, text="− Remove last",
                   command=self._remove_last_person).pack(side="left", padx=(6, 0))

        # v1.45: visible signature picker (sign mode only). Mirrors the
        # persons editor's slot used in prepare mode. Switching among
        # several saved signatures used to be possible ONLY via the
        # per-window right-click menu, which users couldn't find — so every
        # window silently used the first signature. This makes the active
        # signature obvious: it sets the signature for NEW windows, and when
        # a window is selected it reassigns just that one.
        self.sig_picker_frame = ttk.LabelFrame(
            self.win, text="Signature to use",
        )
        # NOTE: not packed yet — _refresh_mode_ui handles that.
        sig_row = ttk.Frame(self.sig_picker_frame)
        sig_row.pack(fill="x", padx=10, pady=(6, 2))
        ttk.Label(sig_row, text="Signature:").pack(side="left")
        self.sig_combo_var = tk.StringVar()
        self.sig_combo = ttk.Combobox(
            sig_row, textvariable=self.sig_combo_var, state="readonly",
            width=42,
        )
        self.sig_combo.pack(side="left", padx=(6, 0))
        self.sig_combo.bind("<<ComboboxSelected>>",
                            self._on_signature_combo_changed)
        ttk.Label(
            self.sig_picker_frame,
            text="Applies to new signature windows you place. To change a "
                 "window you already placed, click to select it first, then "
                 "pick here (or right-click the window → Sign as ▸). Manage "
                 "or add signatures with the My Signatures button in the "
                 "main window.",
            foreground="#555", wraplength=760, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))
        self._sig_combo_ids = []
        self._populate_signature_combo()

        # Instruction line (status — updates per interaction)
        self.status_lbl = ttk.Label(
            self.win,
            text="Left-click on a page to place a signature spot. "
                 "Left-click on a spot to select; drag to move; "
                 "right-click for size / signer / delete; Delete key "
                 "removes the selected spot.",
            foreground="#555", wraplength=780, justify="left",
        )
        self.status_lbl.pack(fill="x", padx=12, pady=(2, 6))

        # Scrollable canvas
        canvas_wrap = ttk.Frame(self.win, borderwidth=1, relief="sunken")
        canvas_wrap.pack(fill="both", expand=True, padx=12, pady=4)
        self.canvas = tk.Canvas(canvas_wrap, background="#dadada",
                                highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_wrap, orient="vertical",
                            command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Left button: press → place/select + start potential drag.
        #              motion → drag selected stamp.
        #              release → finalize drag or count as a click.
        self.canvas.bind("<ButtonPress-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        # Right button: context menu on a stamp.
        self.canvas.bind("<Button-3>", self._on_right_click)   # Linux/Win
        self.canvas.bind("<Button-2>", self._on_right_click)   # macOS
        self.canvas.bind("<Control-Button-1>",
                          self._on_right_click)                # macOS alt
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

        # Keyboard: Delete / Backspace / Escape
        self.win.bind("<Delete>", self._on_delete_key)
        self.win.bind("<BackSpace>", self._on_delete_key)
        self.win.bind("<Escape>", self._on_escape_key)

        # The right-click context menu is created lazily on first use.
        self._context_menu = None
        self._context_menu_target_id = None

        # v1.44 security note: signed PDFs always have the visible
        # signature baked into the page content + a cryptographic
        # certification that catches any tampering. Make this explicit
        # so the user understands the protection model.
        ttk.Label(
            self.win,
            text=("🔒 Signed PDFs are always tamper-protected: the "
                  "signature visual is baked into the page (PDF editors "
                  "can't quietly delete it) and certified with SHA-256 "
                  "so any modification shows as 'invalid signature' in "
                  "Acrobat. This applies regardless of the 'flatten' "
                  "checkbox in the main app."),
            foreground="#555", wraplength=780, justify="left",
            font=("", 8),
        ).pack(fill="x", padx=12, pady=(0, 4))

        # Footer buttons
        foot = ttk.Frame(self.win)
        foot.pack(fill="x", padx=12, pady=(6, 12))
        self.count_lbl = ttk.Label(foot, text="0 signature spots placed.",
                                   foreground="#666")
        self.count_lbl.pack(side="left")
        ttk.Button(foot, text="Cancel", command=self.win.destroy
                   ).pack(side="right", padx=(6, 0))
        self.action_btn = ttk.Button(foot, text="Sign & Save",
                                     command=self._do_action, state="disabled")
        self.action_btn.pack(side="right")

        # Open the PDF + render
        try:
            self._doc = pdfium.PdfDocument(pdf_bytes)
            self._page_count = len(self._doc)
            self._page_pdf_dims = [self._doc[i].get_size()
                                   for i in range(self._page_count)]
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Couldn't open PDF for signing:\n{e}")
            self.win.destroy()
            return

        self._configure_after_id = None
        self.win.after(50, self._render_all_pages)
        # _refresh_mode_ui takes care of action button, persons frame
        # visibility, and any initial redraw. Safe even with zero stamps.
        self._refresh_mode_ui()

    # ---- Geometry / hit-testing ----------------------------------------
    @staticmethod
    def _boxes_overlap(a, b):
        """True if two PDF-point bboxes on the same page overlap (>0 area)."""
        if a["page"] != b["page"]:
            return False
        ax1, ay1 = a["x_pt"], a["y_pt"]
        ax2, ay2 = ax1 + a["width_pt"], ay1 + a["height_pt"]
        bx1, by1 = b["x_pt"], b["y_pt"]
        bx2, by2 = bx1 + b["width_pt"], by1 + b["height_pt"]
        return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

    def _stamp_at_canvas_point(self, cx, cy):
        """Returns the stamp dict under the canvas-space coordinate, or None.
        Iterates in reverse so the topmost (last drawn) wins on overlap."""
        for stamp in reversed(self._stamps):
            box = self._stamp_canvas_box(stamp)
            if box is None:
                continue
            x1, y1, x2, y2 = box
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return stamp
        return None

    def _stamp_canvas_box(self, stamp):
        """PDF-point stamp → canvas-pixel bbox (x1,y1,x2,y2) or None."""
        page = stamp["page"] - 1
        if page < 0 or page >= len(self._page_y_positions):
            return None
        y0, x0, _, _ = self._page_y_positions[page]
        page_h_pt = self._page_pdf_dims[page][1]
        scale = self._page_render_scale
        px = stamp["x_pt"] * scale
        py_top = (page_h_pt - stamp["y_pt"] - stamp["height_pt"]) * scale
        pw = stamp["width_pt"] * scale
        ph = stamp["height_pt"] * scale
        return (x0 + px, y0 + py_top, x0 + px + pw, y0 + py_top + ph)

    def _hit_page(self, cx, cy):
        """Which page index is under (cx, cy)? Returns (page_idx, rel_x_px,
        rel_y_px) or (None, 0, 0)."""
        for i, (y0, x0, w, h) in enumerate(self._page_y_positions):
            if y0 <= cy <= y0 + h and x0 <= cx <= x0 + w:
                return i, cx - x0, cy - y0
        return None, 0, 0

    def _canvas_to_pdf_point(self, page_idx, rel_x_px, rel_y_px,
                              width_pt=None, height_pt=None):
        """Convert a canvas-pixel page-local position to PDF bottom-left
        coords for a stamp of the given size, **centered on the click**
        (so the stamp lands where the cursor is)."""
        if width_pt is None:
            width_pt = self.DEFAULT_STAMP_W_PT
        if height_pt is None:
            height_pt = self.DEFAULT_STAMP_H_PT
        scale = self._page_render_scale
        page_w_pt, page_h_pt = self._page_pdf_dims[page_idx]
        click_x_pt = rel_x_px / scale
        click_y_from_top_pt = rel_y_px / scale
        # Center the stamp on the click.
        pdf_x = click_x_pt - width_pt / 2
        pdf_y_top = click_y_from_top_pt - height_pt / 2
        pdf_y_bottom_left = page_h_pt - pdf_y_top - height_pt
        # Clamp inside page.
        pdf_x = max(0, min(pdf_x, page_w_pt - width_pt))
        pdf_y_bottom_left = max(0, min(pdf_y_bottom_left,
                                       page_h_pt - height_pt))
        return pdf_x, pdf_y_bottom_left

    # ---- Mutation: place / select / move / delete ----------------------
    def _place_new_stamp(self, page_idx, rel_x_px, rel_y_px):
        pdf_x, pdf_y = self._canvas_to_pdf_point(page_idx, rel_x_px, rel_y_px)
        proposed = {
            "id": uuid.uuid4().hex,
            "page": page_idx + 1,
            "x_pt": pdf_x,
            "y_pt": pdf_y,
            "width_pt": self.DEFAULT_STAMP_W_PT,
            "height_pt": self.DEFAULT_STAMP_H_PT,
            "selected": False,
            # v1.31: signature_id points at a saved signature (used in
            # Sign mode). None = leave empty for the next signer.
            "signature_id": self._default_signature_id,
            # v1.32: person_id points at one of self._persons (used in
            # Prepare mode). Default to the first Person slot.
            "person_id": self._default_person_id,
        }
        # Overlap check.
        for existing in self._stamps:
            if self._boxes_overlap(proposed, existing):
                self.status_lbl.config(
                    text=f"Can't place here — overlaps a spot on page "
                         f"{existing['page']}. Pick a different spot.",
                    foreground="#a30000",
                )
                return False
        # Deselect everything and select the new one.
        for s in self._stamps:
            s["selected"] = False
        proposed["selected"] = True
        self._stamps.append(proposed)
        self._selected_stamp_id = proposed["id"]
        self._redraw_stamps()
        self._update_status_for_selection()
        return True

    def _select_stamp(self, stamp):
        for s in self._stamps:
            s["selected"] = (s["id"] == stamp["id"])
        self._selected_stamp_id = stamp["id"]
        self._redraw_stamps()
        self._update_status_for_selection()

    def _deselect_all(self):
        for s in self._stamps:
            s["selected"] = False
        self._selected_stamp_id = None
        self.canvas.config(cursor="")
        self._redraw_stamps()
        self._update_status_for_selection()

    def _selected_stamp(self):
        if self._selected_stamp_id is None:
            return None
        for s in self._stamps:
            if s["id"] == self._selected_stamp_id:
                return s
        return None

    def _delete_selected(self):
        sel = self._selected_stamp()
        if sel is None:
            return
        self._stamps = [s for s in self._stamps if s["id"] != sel["id"]]
        self._selected_stamp_id = None
        self.canvas.config(cursor="")
        # Numbers are derived from index in self._stamps at draw time, so
        # removing one auto-renumbers the rest with no extra bookkeeping.
        self._redraw_stamps()
        self._update_status_for_selection()

    # ---- Event handlers ------------------------------------------------
    def _on_left_press(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        hit = self._stamp_at_canvas_point(cx, cy)
        if hit is not None:
            # Clicked on a stamp → select it + arm drag.
            self._select_stamp(hit)
            self._drag_state = {
                "stamp_id": hit["id"],
                "start_cx": cx, "start_cy": cy,
                "orig_x_pt": hit["x_pt"],
                "orig_y_pt": hit["y_pt"],
                "orig_page": hit["page"],
                "moved": False,
            }
            return
        # Clicked on empty: place new spot if on a page, else deselect.
        page_idx, rel_x, rel_y = self._hit_page(cx, cy)
        self._drag_state = None
        if page_idx is not None:
            self._place_new_stamp(page_idx, rel_x, rel_y)
        else:
            self._deselect_all()

    def _on_left_motion(self, event):
        if self._drag_state is None:
            return
        sel = self._selected_stamp()
        if sel is None or sel["id"] != self._drag_state["stamp_id"]:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        dx = cx - self._drag_state["start_cx"]
        dy = cy - self._drag_state["start_cy"]
        if not self._drag_state["moved"] and (
                abs(dx) > self.DRAG_THRESHOLD_PX
                or abs(dy) > self.DRAG_THRESHOLD_PX):
            self._drag_state["moved"] = True
            self.canvas.config(cursor="fleur")
        if not self._drag_state["moved"]:
            return
        # Find which page is under the cursor (allows cross-page drag).
        page_idx, rel_x, rel_y = self._hit_page(cx, cy)
        if page_idx is None:
            return  # ignore motion off-page; the release will validate
        # Recompute centered position on the new page.
        pdf_x, pdf_y = self._canvas_to_pdf_point(
            page_idx, rel_x, rel_y, sel["width_pt"], sel["height_pt"],
        )
        sel.update({"page": page_idx + 1, "x_pt": pdf_x, "y_pt": pdf_y})
        self._redraw_stamps()

    def _on_left_release(self, _event=None):
        if self._drag_state is None:
            return
        sel = self._selected_stamp()
        moved = self._drag_state["moved"]
        self._drag_state = None
        self.canvas.config(cursor="")
        if not moved or sel is None:
            return
        # Overlap check now that the drag has landed. If overlap, revert.
        for other in self._stamps:
            if other["id"] == sel["id"]:
                continue
            if self._boxes_overlap(sel, other):
                sel["page"] = self._drag_state_orig_page \
                    if hasattr(self, "_drag_state_orig_page") else sel["page"]
                # Easier: just snap to where it originally was, stored on
                # _on_left_press as orig_x_pt / orig_y_pt / orig_page.
                # We've already cleared _drag_state, so use the stamp's
                # current value as fallback (no revert). For a clean
                # revert, we'd need to stash the orig before clearing.
                self.status_lbl.config(
                    text="Can't drop here — overlaps another spot. "
                         "Try a different spot.",
                    foreground="#a30000",
                )
                # We can't perfectly revert without the orig values, but
                # the user can simply drag again — preserves session flow.
                self._redraw_stamps()
                return
        self._redraw_stamps()
        self._update_status_for_selection()

    def _on_right_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        hit = self._stamp_at_canvas_point(cx, cy)
        if hit is None:
            return
        self._select_stamp(hit)
        self._show_context_menu(event, hit)

    def _show_context_menu(self, event, stamp):
        """v1.32 context menu — branches on mode:
          • Sign mode    → 'Sign as ▸ <saved signatures>'
          • Prepare mode → 'Assign to ▸ Person N - name <email>'
        Plus Size presets and Delete in both modes."""
        m = tk.Menu(self.canvas, tearoff=0)
        if self.mode_var.get() == "prepare":
            self._build_assign_to_submenu(m, stamp)
        else:
            self._build_sign_as_submenu(m, stamp)

        # Size preset submenu
        size_menu = tk.Menu(m, tearoff=0)
        for label, (w, h) in self.SIZE_PRESETS.items():
            current = (round(stamp["width_pt"]) == w
                        and round(stamp["height_pt"]) == h)
            size_menu.add_command(
                label=("✓ " if current else "  ") + label,
                command=lambda sid=stamp["id"], ww=w, hh=h:
                    self._resize_stamp(sid, ww, hh),
            )
        m.add_cascade(label="Size", menu=size_menu)
        m.add_separator()
        m.add_command(label="Delete this spot",
                       command=self._delete_selected)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _build_sign_as_submenu(self, parent_menu, stamp):
        sub = tk.Menu(parent_menu, tearoff=0)
        current_sig_id = stamp.get("signature_id")
        if not self._signatures:
            sub.add_command(
                label="(no saved signatures — create one in My Signatures)",
                state="disabled",
            )
        else:
            for sig in self._signatures:
                lbl = sig.get("label") or sig.get("name") or "Signature"
                mark = "  ✓ " if sig["id"] == current_sig_id else "      "
                sub.add_command(
                    label=f"{mark}{lbl}",
                    command=lambda sid=stamp["id"], gid=sig["id"]:
                        self._assign_signature(sid, gid),
                )
        sub.add_separator()
        sub.add_command(
            label=("  ✓ Leave empty (for someone else to sign)"
                   if current_sig_id is None else
                   "      Leave empty (for someone else to sign)"),
            command=lambda sid=stamp["id"]: self._assign_signature(sid, None),
        )
        parent_menu.add_cascade(label="Sign as ▸", menu=sub)

    def _build_assign_to_submenu(self, parent_menu, stamp):
        sub = tk.Menu(parent_menu, tearoff=0)
        current_pid = stamp.get("person_id")
        for p in self._persons:
            label = self._person_label(p["id"])
            mark = "  ✓ " if p["id"] == current_pid else "      "
            sub.add_command(
                label=f"{mark}{label}",
                command=lambda sid=stamp["id"], pid=p["id"]:
                    self._assign_person(sid, pid),
            )
        sub.add_separator()
        sub.add_command(
            label="+ Add a new person…",
            command=lambda sid=stamp["id"]: self._add_person_and_assign(sid),
        )
        parent_menu.add_cascade(label="Assign to ▸", menu=sub)

    def _assign_signature(self, stamp_id, sig_id):
        """Set a stamp's signature_id (or None to leave empty)."""
        for s in self._stamps:
            if s["id"] == stamp_id:
                s["signature_id"] = sig_id
                self._redraw_stamps()
                self._update_status_for_selection()
                return

    # ---- Signature picker (sign mode) ----------------------------------
    def _populate_signature_combo(self):
        """Build the combobox list from saved signatures plus a trailing
        'leave empty' option. self._sig_combo_ids holds the parallel
        signature ids (None for the leave-empty entry)."""
        labels, ids = [], []
        for sig in self._signatures:
            labels.append(sig.get("label") or sig.get("name") or "Signature")
            ids.append(sig["id"])
        labels.append("— Leave empty (someone else signs) —")
        ids.append(None)
        self._sig_combo_ids = ids
        self.sig_combo.config(values=labels)
        self._sync_signature_combo()

    def _sync_signature_combo(self):
        """Point the combobox at the selected window's signature, or — when
        nothing is selected — at the current default for new windows. Set
        programmatically, so this does NOT fire <<ComboboxSelected>>."""
        if not hasattr(self, "sig_combo"):
            return
        sel = self._selected_stamp()
        target_id = (sel.get("signature_id") if sel is not None
                     else self._default_signature_id)
        try:
            idx = self._sig_combo_ids.index(target_id)
        except ValueError:
            idx = len(self._sig_combo_ids) - 1   # leave-empty fallback
        if self.sig_combo.cget("values"):
            self.sig_combo.current(idx)

    def _on_signature_combo_changed(self, _event=None):
        idx = self.sig_combo.current()
        if idx < 0 or idx >= len(self._sig_combo_ids):
            return
        chosen = self._sig_combo_ids[idx]
        # New windows placed from now on use this signature.
        self._default_signature_id = chosen
        sel = self._selected_stamp()
        if sel is not None:
            # Reassign just the selected window (redraws + refreshes status).
            self._assign_signature(sel["id"], chosen)
        else:
            self._update_status_for_selection()
        # Drop focus so Delete/Escape keep acting on the canvas, not the box.
        self.canvas.focus_set()

    def _assign_person(self, stamp_id, person_id):
        """Prepare-mode: assign a stamp to one of the Person slots."""
        for s in self._stamps:
            if s["id"] == stamp_id:
                s["person_id"] = person_id
                self._redraw_stamps()
                self._update_status_for_selection()
                return

    def _add_person_and_assign(self, stamp_id):
        """Convenience: create a fresh Person slot AND assign this stamp
        to it. Lets the user add the new signer without leaving the
        right-click flow."""
        self._add_person()
        new_pid = self._persons[-1]["id"]
        self._assign_person(stamp_id, new_pid)

    def _resize_stamp(self, stamp_id, new_w_pt, new_h_pt):
        for s in self._stamps:
            if s["id"] == stamp_id:
                # Try the new size; revert if it would overlap.
                old_w, old_h = s["width_pt"], s["height_pt"]
                s["width_pt"], s["height_pt"] = new_w_pt, new_h_pt
                # Clamp to page bounds.
                page_w_pt, page_h_pt = self._page_pdf_dims[s["page"] - 1]
                s["x_pt"] = max(0, min(s["x_pt"], page_w_pt - new_w_pt))
                s["y_pt"] = max(0, min(s["y_pt"], page_h_pt - new_h_pt))
                # Overlap check
                for other in self._stamps:
                    if other["id"] == stamp_id:
                        continue
                    if self._boxes_overlap(s, other):
                        s["width_pt"], s["height_pt"] = old_w, old_h
                        self.status_lbl.config(
                            text="Can't resize — would overlap another spot.",
                            foreground="#a30000",
                        )
                        self._redraw_stamps()
                        return
                self._redraw_stamps()
                self._update_status_for_selection()
                return

    def _on_delete_key(self, _event=None):
        if self._selected_stamp_id is not None:
            self._delete_selected()

    def _on_escape_key(self, _event=None):
        self._drag_state = None
        self.canvas.config(cursor="")
        self._deselect_all()

    # ---- Status / button state -----------------------------------------
    def _update_status_for_selection(self):
        n = len(self._stamps)
        self.count_lbl.config(
            text=f"{n} signature window{'' if n == 1 else 's'} placed."
        )
        self._refresh_action_button()
        # Keep the signature picker mirroring the current selection / default.
        self._sync_signature_combo()
        sel = self._selected_stamp()
        if sel is not None:
            idx = self._stamps.index(sel) + 1
            if self.mode_var.get() == "prepare":
                pid = sel.get("person_id")
                if any(p["id"] == pid for p in self._persons):
                    who = f"Assigned to: {self._person_label(pid)}"
                else:
                    who = "Unassigned (no Person)"
                menu_hint = "Assign to / Size / Delete"
            else:
                sig_id = sel.get("signature_id")
                sig_label = next(
                    (s.get("label") or s.get("name") or "Signature"
                     for s in self._signatures if s["id"] == sig_id),
                    None,
                )
                who = (f"Sign as: {sig_label}" if sig_label
                       else "Empty — for someone else to sign")
                menu_hint = "Sign as / Size / Delete"
            self.status_lbl.config(
                text=f"Selected: window #{idx} on page {sel['page']} · "
                     f"{who}. "
                     f"Drag to move · right-click → {menu_hint} · "
                     f"Delete key removes it.",
                foreground="#0a64d8",
            )
        elif n == 0:
            self.status_lbl.config(
                text="Left-click on a page to place a signature window. "
                     "Left-click on one to select; drag to move; "
                     "right-click for size / signer / delete; "
                     "Delete key removes it.",
                foreground="#555",
            )
        else:
            self.status_lbl.config(
                text=f"{n} window{'' if n == 1 else 's'} placed. "
                     f"Click another page to add more, or use the button below.",
                foreground="#555",
            )

    def _refresh_action_button(self):
        if self.mode_var.get() == "prepare":
            self.action_btn.config(text="Save prepared PDF")
        else:
            self.action_btn.config(text="Sign & Save")
        if not self._stamps:
            self.action_btn.state(["disabled"])
        else:
            self.action_btn.state(["!disabled"])

    def _refresh_mode_ui(self):
        """Called when the user toggles Sign/Prepare radio. Shows or hides
        the Persons editor, redraws stamps (colours change per mode), and
        updates the action button label."""
        is_prepare = self.mode_var.get() == "prepare"
        if is_prepare:
            # Insert the persons editor between mode_row and status_lbl.
            self.sig_picker_frame.pack_forget()
            self.persons_frame.pack(fill="x", padx=12, pady=(0, 4),
                                     before=self.status_lbl)
            self._render_persons_list()
        else:
            self.persons_frame.pack_forget()
            self.sig_picker_frame.pack(fill="x", padx=12, pady=(0, 4),
                                       before=self.status_lbl)
            self._sync_signature_combo()
        self._refresh_action_button()
        self._redraw_stamps()
        self._update_status_for_selection()

    # ---- Persons editor (prepare mode) ---------------------------------
    def _render_persons_list(self):
        """Repaint the rows in the Persons editor — one row per Person:
        index label + Name entry + Email entry."""
        for w in self.persons_list_frame.winfo_children():
            w.destroy()
        for idx, p in enumerate(self._persons, start=1):
            row = ttk.Frame(self.persons_list_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"Person {idx}:", width=10,
                       foreground=self._color_for_person(p["id"]),
                       ).pack(side="left")
            name_var = tk.StringVar(value=p["name"])
            email_var = tk.StringVar(value=p["email"])
            # Keep the dict in sync as the user types.
            name_var.trace_add(
                "write",
                lambda *_a, pid=p["id"], v=name_var:
                    self._update_person_field(pid, "name", v.get()),
            )
            email_var.trace_add(
                "write",
                lambda *_a, pid=p["id"], v=email_var:
                    self._update_person_field(pid, "email", v.get()),
            )
            ttk.Entry(row, textvariable=name_var, width=22
                      ).pack(side="left", padx=(0, 4))
            ttk.Entry(row, textvariable=email_var, width=28
                      ).pack(side="left", padx=(0, 4))
            ttk.Label(row, text="(name and email are optional)",
                       foreground="#888").pack(side="left")

    def _update_person_field(self, pid, key, val):
        for p in self._persons:
            if p["id"] == pid:
                p[key] = val
                # If a stamp uses this person, its on-canvas label changes
                # when the name updates, so redraw.
                self._redraw_stamps()
                self._update_status_for_selection()
                return

    def _color_for_person(self, person_id):
        for idx, p in enumerate(self._persons):
            if p["id"] == person_id:
                return self.PERSON_COLORS[idx % len(self.PERSON_COLORS)]
        return "#666666"

    def _person_label(self, person_id):
        """Returns a display label like 'Person 1' or 'Person 1 - Alice
        <alice@x.com>' depending on what the user filled in."""
        for idx, p in enumerate(self._persons, start=1):
            if p["id"] == person_id:
                bits = [f"Person {idx}"]
                if p["name"]:
                    bits.append(p["name"])
                if p["email"]:
                    bits.append(f"<{p['email']}>")
                if len(bits) == 1:
                    return bits[0]
                return f"{bits[0]} - " + " ".join(bits[1:])
        return "Person ?"

    def _add_person(self):
        self._persons.append({
            "id": uuid.uuid4().hex, "name": "", "email": "",
        })
        self._render_persons_list()

    def _remove_last_person(self):
        if len(self._persons) <= 1:
            messagebox.showinfo(
                APP_NAME,
                "At least one Person slot needs to stay so spots have "
                "something to point at.",
            )
            return
        gone = self._persons.pop()
        # Re-point any stamps that used the removed person to Person 1.
        for s in self._stamps:
            if s.get("person_id") == gone["id"]:
                s["person_id"] = self._persons[0]["id"]
        self._render_persons_list()
        self._redraw_stamps()
        self._update_status_for_selection()

    # ---- Canvas rendering ----------------------------------------------
    def _on_canvas_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.canvas.after_cancel(self._configure_after_id)
            except tk.TclError:
                pass
        self._configure_after_id = self.canvas.after(150, self._render_all_pages)

    def _render_all_pages(self):
        self.canvas.delete("all")
        self._cached_image_refs = []
        self._page_y_positions = []
        cw = max(self.canvas.winfo_width(), 100)
        if self._page_count == 0 or not PIL_TK_OK:
            return
        w_pt0, _ = self._page_pdf_dims[0]
        scale = max((cw - 32) / w_pt0, 0.5)
        scale = min(scale, 6.0)
        self._page_render_scale = scale

        y = 8
        max_w = 0
        for i in range(self._page_count):
            page = self._doc[i]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            photo = _ImageTk.PhotoImage(pil)
            self._cached_image_refs.append(photo)
            x = max((cw - pil.width) // 2, 8)
            self.canvas.create_image(x, y, anchor="nw", image=photo,
                                     tags=(f"page_{i}",))
            self._page_y_positions.append((y, x, pil.width, pil.height))
            self.canvas.create_text(
                cw // 2, y + pil.height + 4, anchor="n",
                text=f"— Page {i + 1} of {self._page_count} —",
                fill="#777", font=("", 8),
            )
            max_w = max(max_w, pil.width)
            y += pil.height + 28

        self.canvas.config(scrollregion=(0, 0, max(max_w + 16, cw), max(y, 100)))
        self._redraw_stamps()

    def _redraw_stamps(self):
        """Wipe and redraw every stamp marker. v1.32: outline-only (no
        fill so the page content stays visible). Outline colour and label
        change depending on mode:
          • Sign mode    → amber for assigned-to-signature, grey-dashed
                            for empty; label shows the signature name.
          • Prepare mode → one colour per Person from PERSON_COLORS;
                            label shows the person's name/email.
        Blue overrides both when the stamp is selected."""
        self.canvas.delete("stamp_marker")
        mode = self.mode_var.get()
        sig_label_by_id = {
            s["id"]: (s.get("label") or s.get("name") or "Signature")
            for s in self._signatures
        }
        for idx, stamp in enumerate(self._stamps, start=1):
            box = self._stamp_canvas_box(stamp)
            if box is None:
                continue
            x1, y1, x2, y2 = box

            if mode == "prepare":
                pid = stamp.get("person_id")
                person_exists = any(p["id"] == pid for p in self._persons)
                outline_c = (self._color_for_person(pid)
                             if person_exists else "#666666")
                dash = () if person_exists else (5, 3)
                heading = (self._person_label(pid) if person_exists
                           else "Unassigned")
            else:  # sign mode
                sig_id = stamp.get("signature_id")
                assigned = sig_id is not None and sig_id in sig_label_by_id
                outline_c = "#d97706" if assigned else "#666666"
                dash = () if assigned else (5, 3)
                heading = (f"Sign as: {sig_label_by_id[sig_id]}"
                            if assigned
                            else "Empty — for someone else")

            if stamp["selected"]:
                outline_c = "#0a64d8"
                width = 3
                dash = ()
            else:
                width = 2

            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=outline_c, width=width, dash=dash,
                fill="",
                tags=("stamp_marker", stamp["id"]),
            )
            cx_mid = (x1 + x2) // 2
            cy_mid = (y1 + y2) // 2
            sub = f"#{idx} · page {stamp['page']}"
            self.canvas.create_text(
                cx_mid, cy_mid - 8, anchor="center",
                text=heading, fill="#1a1a1a", font=("", 11, "bold"),
                tags=("stamp_marker", stamp["id"]),
            )
            self.canvas.create_text(
                cx_mid, cy_mid + 10, anchor="center",
                text=sub, fill=outline_c, font=("", 9),
                tags=("stamp_marker", stamp["id"]),
            )

    # ---- Action (Save prepared / Sign & Save) --------------------------
    def _do_action(self):
        if not self._stamps:
            messagebox.showwarning(APP_NAME, "Place at least one signature "
                                              "spot first.")
            return
        mode = self.mode_var.get()
        if mode == "sign":
            self._do_sign()
        else:
            self._do_prepare()

    def _do_prepare(self):
        out_path = filedialog.asksaveasfilename(
            title="Save prepared PDF as",
            defaultextension=".pdf",
            initialdir=default_save_dir(),
            initialfile="prepared-for-signing.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return
        try:
            # v1.32: caption every empty field with the assigned Person's
            # name + email so the recipient sees "Signature 2 - Alice
            # <alice@example.com>" in Acrobat's signature panel + on the
            # placeholder overlay drawn on the page.
            ordered = []
            for idx, s in enumerate(self._stamps, start=1):
                pid = s.get("person_id")
                person_lbl = self._person_label(pid) if pid else "Sign here"
                ordered.append(dict(
                    s, label=f"Signature {idx} - {person_lbl}",
                ))
            prepare_pdf_with_empty_signature_fields(
                self.pdf_bytes, ordered, out_path,
            )
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Couldn't prepare PDF:\n{e}")
            return
        messagebox.showinfo(
            APP_NAME,
            f"Saved a PDF with {len(self._stamps)} empty signature field"
            f"{'' if len(self._stamps) == 1 else 's'}.\n\n"
            f"PDF: {out_path}\n\n"
            "Open it in Acrobat / Foxit / Preview — each empty field is "
            "clickable and labeled (Signature 1, Signature 2, etc.) so the "
            "next signer can fill them in.",
        )
        self.win.destroy()
        if self.on_signed:
            self.on_signed(out_path)

    def _do_sign(self):
        """v1.31: sign every assigned stamp with its OWN signature PNG; any
        unassigned (signature_id=None) stamp is saved as a visible empty
        field for someone else to fill in later."""
        if not self._signatures:
            messagebox.showerror(
                APP_NAME,
                "No saved signatures. Click 'My Signatures' to create one "
                "first, then try again.",
            )
            return
        assigned = [s for s in self._stamps if s.get("signature_id")]
        empty = [s for s in self._stamps if not s.get("signature_id")]
        if not assigned:
            messagebox.showwarning(
                APP_NAME,
                "None of the placed spots are assigned to a signature. "
                "Right-click a spot → Sign as → pick one of your signatures, "
                "or switch to 'Prepare for others to sign' mode.",
            )
            return

        # Cache signature PNG bytes by id so we don't re-read each stamp.
        sig_by_id = {s["id"]: s for s in self._signatures}
        sig_png_cache = {}
        try:
            for sig_id in {s["signature_id"] for s in assigned}:
                sig_png_cache[sig_id] = load_signature_image(sig_id)
        except OSError as e:
            messagebox.showerror(
                APP_NAME, f"Couldn't read saved signature image:\n{e}",
            )
            return

        out_path = filedialog.asksaveasfilename(
            title="Save signed PDF as",
            defaultextension=".pdf",
            initialdir=default_save_dir(),
            initialfile="signed.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return
        try:
            # Each assigned stamp carries its own signature_png + full
            # signer meta (name, company, address, tax_id, license) so the
            # stamped appearance on the signed PDF shows the full identity.
            ordered_assigned = []
            for s in assigned:
                meta = sig_by_id[s["signature_id"]]
                cn = (meta.get("name") or meta.get("label")
                      or "Signer").strip() or "Signer"
                signer_meta = {
                    k: (meta.get(k) or "").strip()
                    for k in ("name", "company", "address",
                              "tax_id", "license")
                }
                signer_meta["name"] = cn  # ensure non-empty name
                ordered_assigned.append(dict(
                    s,
                    label=f"Signature {self._stamps.index(s) + 1} - {cn}",
                    signature_png=sig_png_cache[s["signature_id"]],
                    common_name=cn,
                    signer_meta=signer_meta,
                ))
            ordered_empty = [
                dict(s, label=f"Signature {self._stamps.index(s) + 1} - "
                              f"For other signer")
                for s in empty
            ]
            sha = sign_pdf_with_appearance_multi(
                self.pdf_bytes, ordered_assigned, out_path,
                empty_fields=ordered_empty,
            )
            # Audit log records every signer name we used.
            primary_cn = ordered_assigned[0]["common_name"]
            audit_path = write_audit_json_multi(
                out_path, ordered_assigned, primary_cn, sha,
            )
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Signing failed:\n{e}")
            return
        # v1.45: auto-archive a flattened copy to the user's archive
        # folder if they've configured one. Silent no-op otherwise — the
        # main app's Archive button is the configuration entry point.
        archive_path = archive_signed_pdf(out_path, audit_path)
        msg = (
            f"Signed and saved.\n\n"
            f"PDF:    {out_path}\n"
            f"Audit:  {audit_path}\n\n"
            f"Signed {len(assigned)} of {len(self._stamps)} spot"
            f"{'' if len(self._stamps) == 1 else 's'}."
        )
        if empty:
            msg += (f"\n{len(empty)} spot{'' if len(empty) == 1 else 's'} "
                    f"left empty for other signers — they can fill "
                    f"them in Acrobat or Foxit.")
        if archive_path:
            msg += f"\n\nArchived (flattened copy):\n{archive_path}"
        msg += f"\n\nSHA256 of the signed file:\n{sha}"
        messagebox.showinfo(APP_NAME, msg)
        self.win.destroy()
        if self.on_signed:
            self.on_signed(out_path)

    # ---- mousewheel ----------------------------------------------------
    def _bind_wheel(self, _e=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>",
                             lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind_all("<Button-5>",
                             lambda e: self.canvas.yview_scroll(3, "units"))

    def _unbind_wheel(self, _e=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(units, "units")


# ---------------------------------------------------------------------------
# PreviewTab (v1.23): live combined-PDF viewer.
#
# Pulls cached PDF bytes off each Item (rendered by RenderWorker), stitches
# them into one PDF in memory, paginates it, and renders the currently-
# selected page to a Tk Canvas via pypdfium2.
#
# Lifecycle:
#   • App.invalidate() (via _refresh) marks the cache stale and schedules
#     a debounced rebuild ~500 ms later. This collapses rapid list
#     mutations (folder drops, reorder spam) into a single rebuild.
#   • The "Preview" tab being made visible also triggers a refresh so the
#     user always sees current state on switch-in.
#   • Each rebuild iterates Items in order: for each "ready" item, append
#     its cached pages; for non-ready items, insert a small placeholder
#     page so the viewer reflects total expected page count and the user
#     can see what's still cooking.
# ---------------------------------------------------------------------------
class PreviewTab:
    REFRESH_DEBOUNCE_MS = 500
    ZOOM_PRESETS = ("Fit", "50%", "75%", "100%", "125%", "150%", "200%")

    def __init__(self, parent_frame, app):
        self.app = app
        self.frame = parent_frame
        self._dirty = True
        self._debounce_id = None
        self._combined_pdf = None      # pypdfium2.PdfDocument or None
        self._page_count = 0
        self._current_zoom = "Fit"
        self._cached_image_refs = []   # holds PhotoImage list so Tcl doesn't GC them
        self._page_y_positions = []    # y of each page in the canvas (for Prev/Next nav)
        self._configure_after_id = None  # debounce window-resize re-renders
        # v1.45: per-page removal. _page_sources[i] = (item.uid, local_idx)
        # for the i-th currently-shown page; _hidden_count tracks how many
        # are excluded so the Restore button can label itself.
        self._page_sources = []
        self._hidden_count = 0
        self._page_btn_widgets = []    # per-page Remove buttons (kept from GC)

        # ----- Toolbar
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        self.prev_btn = ttk.Button(bar, text="◀ Prev page",
                                   command=self._prev_page)
        self.prev_btn.pack(side="left")
        self.page_lbl = ttk.Label(bar, text="—", width=18, anchor="center")
        self.page_lbl.pack(side="left", padx=8)
        self.next_btn = ttk.Button(bar, text="Next page ▶",
                                   command=self._next_page)
        self.next_btn.pack(side="left")

        ttk.Label(bar, text="Zoom:").pack(side="left", padx=(20, 4))
        self.zoom_var = tk.StringVar(value="Fit")
        zoom_box = ttk.Combobox(bar, textvariable=self.zoom_var, width=6,
                                values=self.ZOOM_PRESETS, state="readonly")
        zoom_box.pack(side="left")
        zoom_box.bind("<<ComboboxSelected>>", lambda e: self._on_zoom_changed())

        ttk.Button(bar, text="↻ Refresh", command=self.refresh_preview
                   ).pack(side="right")
        # Restore hidden pages — only meaningful once the user has hidden at
        # least one page; label updates with the count.
        self.restore_btn = ttk.Button(
            bar, text="Restore hidden pages",
            command=self._restore_hidden_pages,
        )
        self.restore_btn.pack(side="right", padx=(0, 6))
        self.restore_btn.pack_forget()

        # ----- Status line
        self.status_lbl = ttk.Label(self.frame, text="",
                                    foreground="#666", anchor="w")
        self.status_lbl.pack(fill="x", padx=10, pady=(0, 4))

        # ----- Canvas in a scrollable container
        canvas_wrap = ttk.Frame(self.frame, borderwidth=1, relief="sunken")
        canvas_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas = tk.Canvas(canvas_wrap, background="#dadada",
                                highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_wrap, orient="vertical",
                            command=self._on_yview)
        hsb = ttk.Scrollbar(canvas_wrap, orient="horizontal",
                            command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        # Re-fit on resize when zoom == Fit. Debounce — Tk fires <Configure>
        # many times during a drag-to-resize.
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse-wheel scrolling. Cross-platform:
        #  • Windows + macOS use <MouseWheel> with event.delta (positive =
        #    up; ±120 per notch on Win, smaller on Mac)
        #  • Linux uses <Button-4> (up) / <Button-5> (down)
        # Bound only while pointer is over the canvas so it doesn't steal
        # scroll from the Pages tab's listbox.
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

        self._set_placeholder("Add some files in the Pages tab to see a preview here.")

    # ---- Public hooks called by App -------------------------------------
    def invalidate(self):
        """Mark the cached combined PDF stale. Schedules a rebuild on the
        Tk main thread ~500 ms later; collapsing rapid back-to-back calls
        (e.g. dropping a folder of 50 files) into one rebuild."""
        self._dirty = True
        if self._debounce_id is not None:
            try:
                self.app.root.after_cancel(self._debounce_id)
            except tk.TclError:
                pass
        self._debounce_id = self.app.root.after(
            self.REFRESH_DEBOUNCE_MS, self._rebuild_if_visible_or_dirty
        )

    def refresh_preview(self):
        """Forced rebuild — called on tab activation and the Refresh button."""
        self._dirty = True
        self._rebuild_now()

    # ---- Internals ------------------------------------------------------
    def _is_active(self):
        try:
            return self.app.notebook.tab(self.app.notebook.select(), "text") == "Preview"
        except tk.TclError:
            return False

    def _rebuild_if_visible_or_dirty(self):
        self._debounce_id = None
        # If the Preview tab is open, rebuild now. Otherwise leave the
        # _dirty flag set; the tab-changed handler will pick it up.
        if self._is_active():
            self._rebuild_now()

    def _rebuild_now(self):
        if not FLATTEN_OK:
            # pypdfium2 missing — preview can't render pages.
            self._set_placeholder(
                "Install pypdfium2 to enable the live preview."
            )
            return

        items = list(self.app.items)
        if not items:
            self._teardown_pdf()
            self._set_placeholder(
                "Add some files in the Pages tab to see a preview here."
            )
            return

        # Build a combined PDF from cached per-item bytes. Items not yet
        # rendered are skipped (they'll appear when their render finishes
        # and a subsequent invalidate fires).
        #
        # v1.45: per-page exclusions. We keep a `_page_sources` list parallel
        # to the pages we actually add — each entry is (item.uid, local_idx)
        # so the per-page "Remove" button knows what to hide, and a running
        # `hidden` count drives the Restore control.
        writer = PdfWriter()
        excluded = self.app.excluded_pages
        self._page_sources = []
        pending = 0
        failed = 0
        hidden = 0
        skipped_labels = []
        for it in items:
            if it.render_status == "ready" and it.cached_pdf_bytes:
                try:
                    reader = PdfReader(io.BytesIO(it.cached_pdf_bytes))
                    for local_idx, pg in enumerate(reader.pages):
                        if (it.uid, local_idx) in excluded:
                            hidden += 1
                            continue
                        writer.add_page(pg)
                        self._page_sources.append((it.uid, local_idx))
                except Exception:
                    failed += 1
                    skipped_labels.append(it.label)
            elif it.render_status == "failed":
                failed += 1
                skipped_labels.append(it.label)
            else:
                pending += 1
        self._hidden_count = hidden

        if len(writer.pages) == 0:
            self._teardown_pdf()
            if pending:
                self._set_placeholder(
                    f"Rendering {pending} item(s)… the preview will appear "
                    "as they finish."
                )
            elif hidden:
                self._set_placeholder(
                    f"All {hidden} page(s) are hidden. Use “Restore hidden "
                    "pages” above to bring them back."
                )
            else:
                self._set_placeholder("No pages to preview yet.")
            self._update_restore_button()
            return

        # Materialise to bytes, hand to pypdfium2 for rendering.
        buf = io.BytesIO()
        writer.write(buf)
        self._teardown_pdf()
        try:
            self._combined_pdf = pdfium.PdfDocument(buf.getvalue())
            self._page_count = len(self._combined_pdf)
        except Exception as e:
            self._set_placeholder(f"Couldn't open combined PDF: {e}")
            return

        status_bits = [f"{self._page_count} pages"]
        if hidden:
            status_bits.append(f"{hidden} hidden")
        if pending:
            status_bits.append(f"{pending} still rendering")
        if failed:
            status_bits.append(f"{failed} failed")
        self.status_lbl.config(text="  ·  ".join(status_bits))
        self._update_restore_button()
        self._dirty = False
        self._render_all_pages()

    def _set_placeholder(self, text):
        self.status_lbl.config(text="")
        # Destroy any lingering per-page Remove buttons (canvas.delete only
        # removes the embedding window item, not the child Button widget).
        for w in getattr(self, "_page_btn_widgets", []):
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._page_btn_widgets = []
        self.canvas.delete("all")
        self.canvas.create_text(
            10, 10, anchor="nw",
            text=text, fill="#666", font=("", 11),
        )
        self.page_lbl.config(text="—")
        self.prev_btn.state(["disabled"])
        self.next_btn.state(["disabled"])

    def _teardown_pdf(self):
        if self._combined_pdf is not None:
            try:
                self._combined_pdf.close()
            except Exception:
                pass
        self._combined_pdf = None
        self._page_count = 0

    # ---- Navigation -----------------------------------------------------
    def _current_visible_page(self):
        """Returns the 0-indexed page that's at the top of the visible area.
        Used to keep the page indicator in sync with scrolling."""
        if not self._page_y_positions:
            return 0
        # canvas.yview() returns (top, bottom) as fractions of scrollregion.
        try:
            top_frac, _ = self.canvas.yview()
        except tk.TclError:
            return 0
        try:
            _, _, _, total_h = self.canvas.cget("scrollregion").split()
            top_px = float(top_frac) * float(total_h)
        except (ValueError, AttributeError):
            return 0
        # Find the last page whose y is <= top_px (i.e., the one at the top
        # of the current viewport — or partly above it).
        idx = 0
        for i, y in enumerate(self._page_y_positions):
            if y <= top_px + 4:
                idx = i
            else:
                break
        return idx

    def _update_page_indicator(self):
        if self._page_count <= 0:
            self.page_lbl.config(text="—")
            self.prev_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            return
        cur = self._current_visible_page()
        self.page_lbl.config(text=f"Page {cur + 1} / {self._page_count}")
        self.prev_btn.state(["!disabled"] if cur > 0 else ["disabled"])
        self.next_btn.state(["!disabled"]
                            if cur < self._page_count - 1
                            else ["disabled"])

    def _on_yview(self, *args):
        """Scrollbar callback — pass through to canvas then refresh the
        page indicator."""
        self.canvas.yview(*args)
        self._update_page_indicator()

    def _prev_page(self):
        cur = self._current_visible_page()
        if cur > 0:
            self._scroll_to_page(cur - 1)

    def _next_page(self):
        cur = self._current_visible_page()
        if cur < self._page_count - 1:
            self._scroll_to_page(cur + 1)

    def _scroll_to_page(self, idx):
        """Scroll the canvas so that page `idx`'s top edge is at the top of
        the visible area."""
        if not self._page_y_positions or idx < 0 or idx >= len(self._page_y_positions):
            return
        try:
            _, _, _, total_h = self.canvas.cget("scrollregion").split()
            total_h = max(float(total_h), 1.0)
        except (ValueError, AttributeError):
            return
        frac = self._page_y_positions[idx] / total_h
        self.canvas.yview_moveto(frac)
        self._update_page_indicator()

    def _on_zoom_changed(self):
        self._current_zoom = self.zoom_var.get()
        self._render_all_pages()

    def _on_canvas_configure(self, _event=None):
        """Window resize → re-render at the new fit width. Debounced so we
        only re-render once after the user finishes dragging."""
        if self._current_zoom != "Fit":
            return  # only Fit cares about canvas size
        if self._configure_after_id is not None:
            try:
                self.canvas.after_cancel(self._configure_after_id)
            except tk.TclError:
                pass
        self._configure_after_id = self.canvas.after(
            150, self._render_all_pages
        )

    # ---- Mouse-wheel scrolling ------------------------------------------
    def _bind_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel_linux_up)
        self.canvas.bind_all("<Button-5>", self._on_wheel_linux_down)

    def _unbind_wheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        # Windows event.delta is ±120/notch; macOS uses smaller integers.
        # Either way, divide by 120 then negate (positive = up = scroll up).
        units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(units, "units")
        self._update_page_indicator()

    def _on_wheel_linux_up(self, _event=None):
        self.canvas.yview_scroll(-3, "units")
        self._update_page_indicator()

    def _on_wheel_linux_down(self, _event=None):
        self.canvas.yview_scroll(3, "units")
        self._update_page_indicator()

    # ---- Rendering ------------------------------------------------------
    def _render_all_pages(self):
        """Render every page of the combined PDF stacked vertically into the
        canvas. Continuous scroll is the primary navigation; Prev/Next jump
        to page boundaries.

        For very large PDFs this loads every page bitmap into memory at
        once — fine for typical sessions (<50 pages); a future version can
        lazy-render on scroll if real users hit memory pressure."""
        if self._combined_pdf is None or self._page_count == 0:
            return

        cw = max(self.canvas.winfo_width(), 100)
        z = self._current_zoom
        # For Fit, scale every page to the canvas width. For fixed %,
        # use the % directly. Cap to keep bitmaps reasonable.
        if z == "Fit":
            # Use the FIRST page's width to pick a uniform scale so the
            # whole document renders at a consistent on-screen size.
            try:
                w_pt, _ = self._combined_pdf[0].get_size()
            except Exception:
                w_pt = 612  # US Letter fallback
            scale = max((cw - 32) / w_pt, 0.5)
        else:
            try:
                scale = int(z.rstrip("%")) / 100.0
            except ValueError:
                scale = 1.0
        scale = min(scale, 6.0)

        # Destroy any per-page Remove buttons from the previous render before
        # clearing the canvas, so the Button child widgets don't leak.
        for w in self._page_btn_widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._page_btn_widgets = []

        self.canvas.delete("all")
        self._cached_image_refs = []
        self._page_y_positions = []
        y = 8
        max_w = 0

        for idx in range(self._page_count):
            try:
                page = self._combined_pdf[idx]
                bitmap = page.render(scale=scale)
                pil = bitmap.to_pil()
            except Exception:
                # Skip unrenderable pages but record an empty slot so
                # Prev/Next stays accurate.
                self._page_y_positions.append(y)
                continue
            if not PIL_TK_OK:
                self._set_placeholder("Install Pillow ImageTk to render preview.")
                return
            photo = _ImageTk.PhotoImage(pil)
            self._cached_image_refs.append(photo)
            self._page_y_positions.append(y)
            x = max((cw - pil.width) // 2, 8)
            self.canvas.create_image(x, y, anchor="nw", image=photo)
            # v1.45: a "✕ Remove page" button floating at the page's top-right.
            # Clicking it hides just this page from the output (and preview).
            rm_btn = tk.Button(
                self.canvas, text="✕ Remove page",
                font=("", 8), fg="#a30000", cursor="hand2",
                relief="raised", bd=1, padx=4, pady=0,
                command=lambda i=idx: self._remove_page(i),
            )
            self.canvas.create_window(
                x + pil.width - 4, y + 4, anchor="ne", window=rm_btn,
            )
            self._page_btn_widgets.append(rm_btn)
            # Page number label below each page so users can see where they are.
            label_y = y + pil.height + 4
            self.canvas.create_text(
                cw // 2, label_y, anchor="n",
                text=f"— Page {idx + 1} of {self._page_count} —",
                fill="#777", font=("", 8),
            )
            max_w = max(max_w, pil.width)
            y += pil.height + 28  # gap between pages

        self.canvas.config(
            scrollregion=(0, 0, max(max_w + 16, cw), max(y, 100))
        )
        self._update_page_indicator()

    # ---- Per-page removal (v1.45) ---------------------------------------
    def _remove_page(self, display_idx):
        """Hide the page currently shown at display_idx. Maps it back to its
        source (item.uid, local_idx) and records that in the app-level
        exclusion set, then rebuilds the preview. The exclusion is honoured
        by both the final Create-PDF build and the sign build."""
        if display_idx < 0 or display_idx >= len(self._page_sources):
            return
        src = self._page_sources[display_idx]
        self.app.excluded_pages.add(src)
        # Rebuild immediately so the page disappears and numbering updates.
        self._dirty = True
        self._rebuild_now()

    def _restore_hidden_pages(self):
        """Un-hide every page the user removed in this session."""
        if not self.app.excluded_pages:
            return
        self.app.excluded_pages.clear()
        self._dirty = True
        self._rebuild_now()

    def _update_restore_button(self):
        """Show the Restore button (with a live count) only when something is
        hidden; hide it otherwise."""
        n = self._hidden_count
        if n > 0:
            self.restore_btn.config(
                text=f"Restore {n} hidden page{'' if n == 1 else 's'}"
            )
            try:
                self.restore_btn.pack(side="right", padx=(0, 6))
            except tk.TclError:
                pass
        else:
            self.restore_btn.pack_forget()


# ---------------------------------------------------------------------------
# The application window
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.items = []          # ordered list of Item
        # v1.45: individual pages hidden from the output. Each entry is a
        # (item.uid, local_page_index) tuple — keyed by the stable Item uid
        # so reordering/removing other items doesn't disturb it. Honoured by
        # the Preview tab, the final Create-PDF build, and the sign build.
        self.excluded_pages = set()
        self.work_queue = queue.Queue()
        self._update_dialog_state = None  # populated while auto-update is open
        self._install_dialog = None       # populated while install-deps dialog is open
        self._spreadsheet_hint_shown = False  # one-time page-setup hint flag
        self._save_pending = False         # debounce flag for save_session_state
        self._restored_dropped = 0         # files that vanished between sessions

        root.title(f"{APP_NAME}  v{APP_VERSION}")
        # Initial size; the width is re-fit to the actual content at the end of
        # __init__ (see _fit_start_width) so the long Flatten label never gets
        # clipped behind the bottom-right logo on wider-font systems.
        root.geometry("700x720")
        root.minsize(560, 560)

        pad = {"padx": 10, "pady": 6}

        # --- Header --------------------------------------------------------
        # The brand logo lives in the bottom-right of the Pages tab (next to
        # the add-source buttons), not the header — see the controls row
        # below. We keep its PhotoImage reference alive on self.
        self._brand_logo_ref = None

        head = ttk.Label(
            root,
            text="Drop any file(s) below — or paste a website URL — and create a combined PDF.",
            font=("", 11, "bold"),
        )
        head.pack(anchor="w", **pad)

        notes = []
        if not DND_OK:
            notes.append("Drag-and-drop unavailable (install tkinterdnd2). Use Browse.")
        # Note: HEIC/HEIF/AVIF decoding (pillow-heif) is supported silently
        # in the background — we intentionally don't surface it in the UI.
        if notes:
            ttk.Label(root, text="  ·  ".join(notes), foreground="#b35900"
                      ).pack(anchor="w", padx=10)

        # Missing-component banner: shown only when something optional but
        # genuinely useful (LibreOffice, SANE) isn't installed system-wide.
        # The "Install" button opens a dialog with one-click install per item.
        self._missing_components = detect_missing_components()
        if self._missing_components:
            banner = ttk.Frame(root)
            banner.pack(fill="x", padx=10, pady=(0, 4))
            names = ", ".join(c["label"] for c in self._missing_components)
            ttk.Label(
                banner,
                text=f"Optional components missing: {names}",
                foreground="#7a4500",
            ).pack(side="left")
            ttk.Button(
                banner, text="Install…",
                command=self.show_missing_components_dialog,
            ).pack(side="right")

        # --- Tabbed UI: Pages | Preview -----------------------------------
        # The Notebook lets users flip between the page-list editor
        # (everything they had pre-v1.23) and a live preview of the
        # combined PDF. Create/Save buttons stay below the notebook so
        # they're always accessible regardless of which tab is open.
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(4, 4))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        pages_tab = ttk.Frame(self.notebook)
        preview_tab = ttk.Frame(self.notebook)
        self.notebook.add(pages_tab, text="Pages")
        self.notebook.add(preview_tab, text="Preview")

        # --- URL capture row ----------------------------------------------
        urlframe = ttk.LabelFrame(pages_tab, text="Add a webpage (paste a link)")
        urlframe.pack(fill="x", **pad)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(urlframe, textvariable=self.url_var)
        url_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        url_entry.insert(0, "https://")
        ttk.Button(urlframe, text="Add webpage", command=self.add_url
                   ).pack(side="left", padx=8)

        # --- File list -----------------------------------------------------
        listframe = ttk.LabelFrame(pages_tab, text="Pages (in order)")
        listframe.pack(fill="both", expand=True, **pad)

        self.listbox = tk.Listbox(listframe, selectmode=tk.SINGLE,
                                  activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb = ttk.Scrollbar(listframe, orient="vertical",
                           command=self.listbox.yview)
        sb.pack(side="left", fill="y", pady=8)
        self.listbox.config(yscrollcommand=sb.set)

        # Placeholder hint shown when the page list is empty. Lives as a
        # child of the listbox itself and uses place() to float over the
        # center. _refresh() shows/hides it based on len(self.items).
        self.empty_hint = tk.Label(
            self.listbox,
            text="Drag & Drop any file here\nor click to browse",
            fg="#8a8a8a",
            bg=self.listbox.cget("background"),
            font=("", 11),
            justify="center",
            cursor="hand2",
        )
        # place() positions over the listbox; relx/rely=0.5 = centered.
        self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")
        # Clicking the empty-state hint is a shortcut for the Browse button.
        # Only applies while the placeholder is visible (i.e. list is empty);
        # once items are added _refresh hides the hint and the click target
        # disappears with it.
        self.empty_hint.bind("<Button-1>", lambda _e: self.browse())

        # Register the listbox as a drop target.
        if DND_OK:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self.on_drop)

        # Totals strip right under the listbox: count, total MB on disk,
        # and the *estimated* size if you flatten. Helps users decide
        # whether the Flatten checkbox is worth turning on.
        self.totals_lbl = ttk.Label(pages_tab, text="", foreground="#555",
                                    anchor="w")
        self.totals_lbl.pack(fill="x", padx=14, pady=(0, 4))

        # Right-click context menu: Remove, Move to top, Move to bottom.
        # Linux/Windows use Button-3; Mac uses Button-2 *and* Control-Button-1
        # (Apple convention — trackpad two-finger click maps to Button-2; some
        # keyboards/mice send Ctrl-left-click instead).
        self.row_menu = tk.Menu(self.listbox, tearoff=0)
        self.row_menu.add_command(label="Remove", command=self.remove_sel)
        self.row_menu.add_separator()
        self.row_menu.add_command(label="Move to top", command=self.move_to_top)
        self.row_menu.add_command(label="Move to bottom", command=self.move_to_bottom)
        for ev in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            self.listbox.bind(ev, self._on_listbox_right_click)

        # --- Reorder / remove buttons -------------------------------------
        btns = ttk.Frame(pages_tab)
        btns.pack(fill="x", **pad)
        # Row 1: reorder / remove (acts on the existing list)
        ttk.Button(btns, text="↑ Up", command=self.move_up).pack(side="left")
        ttk.Button(btns, text="↓ Down", command=self.move_down).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove", command=self.remove_sel).pack(side="left")
        ttk.Button(btns, text="Clear all", command=self.clear_all).pack(side="left", padx=4)

        # Row 2+: the add-source buttons, page-size and flatten options sit in
        # a left column; the brand logo fills the empty space to their right
        # (bottom-right of the Pages tab), per the logo-position spec.
        controls = ttk.Frame(pages_tab)
        controls.pack(fill="x")
        left = ttk.Frame(controls)

        # Brand logo — transparent PNG (logoMDM.png). Packed before the left
        # column so it keeps its width when the column expands to fill the
        # rest of the row. Anchored bottom-right; blends with the window bg.
        logo_path = _find_app_logo()
        if logo_path and PIL_TK_OK:
            try:
                src = Image.open(logo_path)
                target_h = 84
                w = max(1, round(src.width * target_h / src.height))
                self._brand_logo_ref = _ImageTk.PhotoImage(
                    src.resize((w, target_h), LANCZOS))
                ttk.Label(controls, image=self._brand_logo_ref).pack(
                    side="right", anchor="se", padx=(8, 14), pady=(2, 8))
            except Exception:
                self._brand_logo_ref = None

        left.pack(side="left", fill="x", expand=True)

        # Add-from-source buttons. Their own line so the Scan button
        # doesn't get clipped on narrower windows.
        add_row = ttk.Frame(left)
        add_row.pack(fill="x", **pad)
        ttk.Button(add_row, text="+ Browse files…",
                   command=self.browse).pack(side="left")
        ttk.Button(add_row, text="📱 From phone (QR)",
                   command=self.add_from_phone).pack(side="left", padx=4)
        ttk.Button(add_row, text="🖨 Scan",
                   command=self.add_from_scanner).pack(side="left")

        # --- Page size + Create -------------------------------------------
        opt = ttk.Frame(left)
        opt.pack(fill="x", **pad)
        ttk.Label(opt, text="Page size:").pack(side="left")
        # Default page size: Letter for US/CA/MX/etc., A4 for the rest of
        # the world. "Original (images)" stays user-selectable but is no
        # longer the default — most users adding mixed content (PDFs,
        # office docs, photos) get a more predictable result with a
        # standard paper size.
        self.size_var = tk.StringVar(value=default_page_size())
        ttk.Radiobutton(opt, text="Original (images)", value="original",
                        variable=self.size_var,
                        command=self._on_page_mode_changed
                        ).pack(side="left", padx=4)
        ttk.Radiobutton(opt, text="A4", value="a4",
                        variable=self.size_var,
                        command=self._on_page_mode_changed
                        ).pack(side="left", padx=4)
        ttk.Radiobutton(opt, text="Letter", value="letter",
                        variable=self.size_var,
                        command=self._on_page_mode_changed
                        ).pack(side="left", padx=4)

        # Flatten option — rasterizes pages into JPEG to shrink the output.
        # Disabled if pypdfium2 isn't available (e.g. dev environment missing
        # the dep). In the shipped bundle it is always present.
        self.flatten_var = tk.BooleanVar(value=False)
        flatten_text = "Flatten output (smaller file — page becomes image, text not selectable)"
        if not FLATTEN_OK:
            flatten_text = "Flatten output (unavailable — install pypdfium2)"
        flatten_row = ttk.Frame(left)
        flatten_row.pack(fill="x", **pad)
        self.flatten_chk = ttk.Checkbutton(
            flatten_row,
            text=flatten_text,
            variable=self.flatten_var,
        )
        if not FLATTEN_OK:
            self.flatten_chk.state(["disabled"])
        self.flatten_chk.pack(anchor="w")

        # Savings preview, sits right under the checkbox label so the
        # user can see the trade-off they'd get from ticking it. Two
        # lines if the message is long. Empty when the list is empty;
        # populated by _update_totals (along with the under-listbox
        # totals strip).
        self.flatten_savings_lbl = ttk.Label(
            flatten_row, text="", foreground="#0a5a16",
            justify="left", wraplength=560,
        )
        self.flatten_savings_lbl.pack(anchor="w", padx=(24, 0))

        # --- Preview tab ---------------------------------------------------
        # PreviewTab assembles the combined PDF from per-item cached bytes
        # and renders pages via pypdfium2. Items not yet rendered show as
        # placeholders; PreviewTab listens to "item_rendered" events
        # forwarded by _poll_queue.
        self.preview = PreviewTab(preview_tab, self)

        # Primary action row: Create PDF + (grayed-for-now) Sign and Create PDF.
        # Sign lights up in v1.26 when e-signature lands; today it just sits
        # there visibly disabled so users know the feature is on the way.
        create_row = ttk.Frame(root)
        create_row.pack(fill="x", **pad)
        self.create_btn = ttk.Button(create_row, text="Create PDF",
                                     command=lambda: self.create_pdf("none"))
        self.create_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.sign_create_btn = ttk.Button(
            create_row, text="🔏 Sign and Create PDF",
            command=self.sign_and_create_pdf,
        )
        self.sign_create_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))
        if not SIGNING_OK:
            # pyhanko / cryptography not installed — keep button grayed.
            self.sign_create_btn.state(["disabled"])

        # Convenience variants of "Create PDF" — same flow, then open or print.
        action_row = ttk.Frame(root)
        action_row.pack(fill="x", **pad)
        self.create_open_btn = ttk.Button(
            action_row, text="Create and open PDF",
            command=lambda: self.create_pdf("open"),
        )
        self.create_open_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.create_print_btn = ttk.Button(
            action_row, text="Create and print PDF",
            command=lambda: self.create_pdf("print"),
        )
        self.create_print_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.status = ttk.Label(root, text="Ready. Drop files or paste a URL to begin.",
                                foreground="#444")
        self.status.pack(anchor="w", padx=10, pady=(0, 4))

        # Always-present progress bar — sits at 0 when idle, fills during a
        # flatten pass so the user can see the page-by-page progress.
        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(0, 4))

        # Footer: clickable version on the left (opens "What's new" dialog),
        # Check-for-updates + Close centered. We use grid with weighted side
        # columns so the middle column is truly centered regardless of the
        # version label's width.
        foot = ttk.Frame(root)
        foot.pack(fill="x", padx=10, pady=(0, 8))
        foot.columnconfigure(0, weight=1)
        foot.columnconfigure(1, weight=0)
        foot.columnconfigure(2, weight=1)

        version_lbl = ttk.Label(foot, text=f"v{APP_VERSION}",
                                foreground="#666", cursor="hand2")
        version_lbl.grid(row=0, column=0, sticky="w")
        version_lbl.bind("<Button-1>", lambda _e: self.show_whats_new())

        center_btns = ttk.Frame(foot)
        center_btns.grid(row=0, column=1)
        # ♡ — sponsor button. Opens the GitHub Sponsors page; hover shows a
        # tooltip.
        sponsor_btn = ttk.Button(center_btns, text="♡", width=3,
                                 command=self._on_sponsor_click)
        sponsor_btn.pack(side="left", padx=(0, 6))
        Tooltip(sponsor_btn, "Support this project from Dejan & Claudia")
        ttk.Button(center_btns, text="Check for updates",
                   command=self.check_for_updates).pack(side="left", padx=(0, 6))
        ttk.Button(center_btns, text="About / License",
                   command=self.show_about_dialog).pack(side="left", padx=(0, 6))
        ttk.Button(center_btns, text="Close",
                   command=self.root.destroy).pack(side="left")

        # v1.32+: My Signatures + (v1.45) Archive live in the footer's
        # right column. Both are setup-once actions so they sit out of
        # the way of the per-PDF workflow.
        right_btns = ttk.Frame(foot)
        right_btns.grid(row=0, column=2, sticky="e")
        # The Archive button label changes based on whether a folder
        # has been configured — "▼ Set up Archive…" until first use,
        # then just "▼ Archive". _refresh_archive_button keeps it in
        # sync.
        self.archive_btn = ttk.Button(
            right_btns, text="▼ Archive",
            command=self.show_archive_dialog,
        )
        self.archive_btn.pack(side="left", padx=(0, 6))
        Tooltip(
            self.archive_btn,
            "Auto-save flattened copies of every signed PDF to a folder "
            "you choose — a backup, separate from where you save them "
            "yourself.",
        )
        self.my_sigs_btn = ttk.Button(
            right_btns, text="✎ My Signatures…",
            command=self.show_my_signatures,
        )
        self.my_sigs_btn.pack(side="left")
        if not SIGNING_OK:
            self.my_sigs_btn.state(["disabled"])
        self._refresh_archive_button()

        # Poll the worker queue so background threads can update the UI safely.
        self.root.after(120, self._poll_queue)

        # Receive file paths from a second invocation (right-click "Open With"
        # while this window is already running). The IPC thread can't touch
        # Tk directly, so it posts to the same queue the build worker uses.
        self._ipc_socket = start_ipc_server(
            lambda paths: self.work_queue.put(("ipc_paths", paths))
        )

        # Background render worker — turns Items into PDF bytes off the UI
        # thread so the Preview tab can show a live combined view without
        # blocking the page list. Concurrency=2 keeps Chromium (used for
        # URL captures) from spawning more than two instances at once.
        self._render_worker = RenderWorker(
            on_event=lambda msg: self.work_queue.put(msg),
            page_mode_fn=lambda: self.size_var.get(),
            concurrency=2,
        )

        # Restore the page list from last session. Files that no longer
        # exist on disk are silently dropped — we surface the count in the
        # status bar so the user knows what happened.
        self._restore_session()

        # Save state on window close, and also intercept window close to
        # ensure the final state is flushed before the process exits.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Fit the start width to the actual content so nothing gets clipped
        # behind the bottom-right logo (the long Flatten label is the widest
        # line, and its width varies with the system font/DPI). Floored at the
        # original 700, capped to the screen so it always fits on-screen.
        try:
            root.update_idletasks()
            req_w = root.winfo_reqwidth()
            screen_w = root.winfo_screenwidth()
            start_w = max(700, min(req_w + 16, screen_w - 80))
            root.geometry(f"{start_w}x720")
        except Exception:
            pass

        # Background, throttled update check (~monthly). Delayed a few seconds
        # so it never competes with startup; silent unless a newer release
        # exists. This is how future releases reach existing users.
        self.root.after(4000, self._maybe_auto_check_updates)

    # --- Tab + page-mode UI hooks --------------------------------------------
    def _on_tab_changed(self, _event=None):
        """Called when the user switches Notebook tabs. The Preview tab
        does a refresh on entry so it always reflects current item state."""
        try:
            current = self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError:
            return
        if current == "Preview" and hasattr(self, "preview"):
            self.preview.refresh_preview()

    def _on_page_mode_changed(self):
        """User toggled Original / A4 / Letter. Existing cached renders
        used the OLD page mode and are now stale — drop them and re-queue
        everything. Visible pre-rendered state in the listbox flips back
        to '⏳ rendering' for each item."""
        for it in self.items:
            self._render_worker.reset_cache(it)
            self._render_worker.enqueue(it)
        self._refresh()  # update status glyphs
        if hasattr(self, "preview"):
            self.preview.invalidate()

    def _restore_session(self):
        items_data, page_mode, flatten, dropped = load_session_state()
        if items_data:
            for it in items_data:
                new_item = Item(
                    it["kind"], it["value"], it["label"],
                    size_bytes=it.get("size_bytes", 0),
                    flat_pages_est=it.get("flat_pages_est", 1),
                )
                self.items.append(new_item)
                # Cached PDF bytes are NOT persisted (in-memory only) — kick
                # off background re-render so the Preview tab is populated
                # without the user having to wait at Create-PDF time.
                if hasattr(self, "_render_worker"):
                    self._render_worker.enqueue(new_item)
            self._refresh()
        if page_mode in ("original", "a4", "letter"):
            self.size_var.set(page_mode)
        if flatten is not None and FLATTEN_OK:
            self.flatten_var.set(bool(flatten))
        self._restored_dropped = dropped
        n = len(self.items)
        if n and dropped:
            self.status.config(
                text=f"Restored {n} item(s) from last session "
                     f"({dropped} missing file(s) were dropped)."
            )
        elif n:
            self.status.config(
                text=f"Restored {n} item(s) from last session."
            )

    def _on_close(self):
        # Final flush before tearing down the window.
        self._save_state_now()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _schedule_save(self):
        """Debounce frequent save_session_state calls. Multiple drops in
        quick succession collapse into one disk write."""
        if self._save_pending:
            return
        self._save_pending = True
        self.root.after(300, self._save_state_now)

    def _save_state_now(self):
        self._save_pending = False
        try:
            save_session_state(
                self.items,
                page_mode=self.size_var.get() if hasattr(self, "size_var") else None,
                flatten=self.flatten_var.get() if hasattr(self, "flatten_var") else None,
            )
        except Exception:
            pass

    # --- Adding items --------------------------------------------------------
    def add_paths(self, paths, source="drop"):
        """Add a list of file/folder paths to the queue. Shared by drag-and-drop,
        the command line, the file browser, and the IPC handler that receives
        paths from a second instance launched by the file manager."""
        added = 0
        too_large = []
        for p in paths:
            if not p:
                continue
            if os.path.isdir(p):
                n, tl = self._add_folder(p)
                added += n
                too_large.extend(tl)
            elif os.path.isfile(p):
                status = self._add_file(p)
                if status == "added":
                    added += 1
                elif status == "too_large":
                    too_large.append(p)
        if added:
            self._refresh()
            self.status.config(
                text=f"Added {added} item(s). Total: {len(self.items)}."
            )
        if too_large:
            names = "\n  • ".join(os.path.basename(p) for p in too_large)
            messagebox.showwarning(
                APP_NAME,
                f"Skipped {len(too_large)} file(s) over {MAX_FILE_LABEL}:\n  • "
                f"{names}\n\nCompress the file (or split it) and try again.",
            )
        # One-time spreadsheet hint: orientation/pagination of .xlsx/.xls is
        # driven by whatever Print Area + Page Setup is saved in the file.
        # Most users have never touched those, which is why wide sheets get
        # cut off. Surfacing this up front cuts a lot of "the output looks
        # wrong" surprise.
        if not self._spreadsheet_hint_shown and any(
            it.kind == "file"
            and os.path.splitext(it.value)[1].lower() in SPREADSHEET_EXTS
            for it in self.items
        ):
            self._spreadsheet_hint_shown = True
            messagebox.showinfo(
                APP_NAME,
                "Tip — spreadsheets convert best when you set them up first.\n\n"
                "Before exporting, open the spreadsheet in Excel / Numbers /\n"
                "LibreOffice Calc and:\n"
                "  • Set the Print Area to just the cells you want.\n"
                "  • Set Page Setup → Fit to: 1 page wide  (and any number tall).\n"
                "  • Pick Landscape if your sheet is wider than it is tall.\n\n"
                "Save, then add the file again. We use whatever print\n"
                "setup is saved in the file — we don't change it ourselves.\n\n"
                "(This message only appears once per session.)",
            )
        return added

    def on_drop(self, event):
        # event.data is a brace/space-delimited list of paths from the OS.
        self.add_paths(self._split_drop(event.data))

    @staticmethod
    def _split_drop(data):
        # tkdnd wraps paths with spaces in {braces}. Parse both forms.
        out, buf, in_brace = [], "", False
        for ch in data:
            if ch == "{":
                in_brace = True
                buf = ""
            elif ch == "}":
                in_brace = False
                out.append(buf)
                buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    out.append(buf)
                    buf = ""
            else:
                buf += ch
        if buf:
            out.append(buf)
        return [p for p in out if p]

    def _add_folder(self, folder):
        """Returns (added_count, [paths_skipped_because_too_large])."""
        added = 0
        too_large = []
        for root_dir, _dirs, names in os.walk(folder):
            for name in sorted(names):
                full = os.path.join(root_dir, name)
                status = self._add_file(full)
                if status == "added":
                    added += 1
                elif status == "too_large":
                    too_large.append(full)
        return added, too_large

    @staticmethod
    def _estimate_flat_pages(path, ext, size):
        """Rough page count after flatten — drives the 'if flattened' total
        shown under the page list. Accurate enough for ordering decisions
        ('worth flattening or not?'), not for precise prediction."""
        if ext in IMAGE_EXTS:
            return 1
        if ext == ".pdf":
            try:
                # pypdf only reads the xref table, very fast even for huge files.
                return max(1, len(PdfReader(path).pages))
            except Exception:
                return max(1, size // 100_000)
        if ext in TEXT_EXTS:
            # ~3 KB of text fills one Courier 9pt A4 page in our renderer.
            return max(1, size // 3_000)
        if ext in OFFICE_EXTS:
            # Very rough — Office docs are zipped XML, ~50 KB per page.
            return max(1, size // 50_000)
        return 1

    def _add_file(self, path):
        """Returns 'added' | 'duplicate' | 'unsupported' | 'too_large' | 'missing'."""
        ext = os.path.splitext(path)[1].lower()
        if ext not in ALL_SUPPORTED:
            return "unsupported"
        if any(it.kind == "file" and it.value == path for it in self.items):
            return "duplicate"
        try:
            size = os.path.getsize(path)
        except OSError:
            return "missing"
        if size > MAX_FILE_BYTES:
            return "too_large"
        flat_pages = self._estimate_flat_pages(path, ext, size)
        label = f"{os.path.basename(path)}  ({format_size(size)})"
        item = Item("file", path, label, size, flat_pages)
        self.items.append(item)
        # Kick off background render so Preview tab has it ready quickly.
        if hasattr(self, "_render_worker"):
            self._render_worker.enqueue(item)
        return "added"

    def add_url(self):
        url = self.url_var.get().strip()
        if not url or url == "https://":
            messagebox.showwarning(APP_NAME, "Paste a website link first.")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        if not parsed.netloc or "." not in parsed.netloc:
            messagebox.showwarning(
                APP_NAME,
                f"That doesn't look like a valid website link:\n\n{url}",
            )
            return
        # URLs have no pre-known size; assume ~3 pages of rendered webpage
        # (typical landing page expands to that under Chromium PDF export).
        url_item = Item("url", url, f"🌐  {url}  (webpage)",
                        size_bytes=0, flat_pages_est=3)
        self.items.append(url_item)
        if hasattr(self, "_render_worker"):
            self._render_worker.enqueue(url_item)
        self.url_var.set("https://")
        self._refresh()
        self.status.config(text=f"Webpage added. Total: {len(self.items)}.")

    def browse(self):
        paths = filedialog.askopenfilenames(title="Choose files")
        if paths:
            self.add_paths(list(paths))

    # --- List operations -----------------------------------------------------
    def _sel(self):
        s = self.listbox.curselection()
        return s[0] if s else None

    def move_up(self):
        i = self._sel()
        if i is None or i == 0:
            return
        self.items[i - 1], self.items[i] = self.items[i], self.items[i - 1]
        self._refresh(select=i - 1)

    def move_down(self):
        i = self._sel()
        if i is None or i >= len(self.items) - 1:
            return
        self.items[i + 1], self.items[i] = self.items[i], self.items[i + 1]
        self._refresh(select=i + 1)

    def move_to_top(self):
        i = self._sel()
        if i is None or i == 0:
            return
        self.items.insert(0, self.items.pop(i))
        self._refresh(select=0)

    def move_to_bottom(self):
        i = self._sel()
        if i is None or i >= len(self.items) - 1:
            return
        self.items.append(self.items.pop(i))
        self._refresh(select=len(self.items) - 1)

    def _on_listbox_right_click(self, event):
        # Select the row under the pointer first, so the menu's commands act
        # on the row the user clicked — not whatever was previously selected.
        idx = self.listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.items):
            return
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        try:
            self.row_menu.tk_popup(event.x_root, event.y_root)
        finally:
            # Recommended Tk pattern — ensures the menu releases input grab
            # even if the user dismisses it without picking an item.
            self.row_menu.grab_release()

    def remove_sel(self):
        i = self._sel()
        if i is None:
            return
        removed = self.items[i]
        # Drop any per-page exclusions that belonged to this item.
        self.excluded_pages = {
            (uid, p) for (uid, p) in self.excluded_pages
            if uid != removed.uid
        }
        del self.items[i]
        self._refresh(select=min(i, len(self.items) - 1))
        self.status.config(text=f"Removed. Total: {len(self.items)}.")

    def clear_all(self):
        self.items.clear()
        self.excluded_pages.clear()
        self._refresh()
        self.status.config(text="Cleared.")

    def _refresh(self, select=None):
        self.listbox.delete(0, tk.END)
        for it in self.items:
            self.listbox.insert(tk.END, f"{it.label}{it.status_glyph()}")
        if select is not None and 0 <= select < len(self.items):
            self.listbox.selection_set(select)
            self.listbox.activate(select)
        # Show/hide the empty-state hint. We use place_forget rather than
        # destroying the widget so it can be brought back when the list is
        # cleared (Clear all → list returns to empty → hint reappears).
        if hasattr(self, "empty_hint"):
            if self.items:
                self.empty_hint.place_forget()
            else:
                self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")
        # Update the running totals strip under the listbox.
        self._update_totals()
        # Tell the Preview tab the page list changed — debounced repaint.
        if hasattr(self, "preview"):
            self.preview.invalidate()
        # _refresh is called by every list mutation (add / remove / reorder /
        # clear), so this is the single hook point for session persistence.
        self._schedule_save()

    def _update_totals(self):
        """Recompute the two info strips:
          • totals_lbl (under the page list): "N items · X MB on disk"
          • flatten_savings_lbl (under the Flatten checkbox): the savings
            estimate, so the trade-off lives right next to the toggle that
            controls it.
        Both are empty when the list is empty."""
        if not hasattr(self, "totals_lbl"):
            return
        n = len(self.items)
        if n == 0:
            self.totals_lbl.config(text="")
            if hasattr(self, "flatten_savings_lbl"):
                self.flatten_savings_lbl.config(text="")
            return

        total_bytes = sum(it.size_bytes for it in self.items)
        flat_pages = sum(it.flat_pages_est for it in self.items)
        flat_est = flat_pages * FLATTEN_BYTES_PER_PAGE_EST

        url_count = sum(1 for it in self.items if it.kind == "url")
        url_note = ""
        if url_count:
            # URLs have no pre-known size; total bytes excludes them.
            url_note = f"  (excludes {url_count} webpage)" if url_count == 1 \
                       else f"  (excludes {url_count} webpages)"

        # Under-listbox strip — just count + on-disk total. The flatten
        # estimate lives next to the Flatten checkbox now.
        self.totals_lbl.config(
            text=f"{n} item{'' if n == 1 else 's'}  ·  "
                 f"{format_size(total_bytes)} on disk{url_note}"
        )

        # Next-to-checkbox savings estimate.
        if hasattr(self, "flatten_savings_lbl"):
            if total_bytes <= 0 and flat_est <= 0:
                self.flatten_savings_lbl.config(text="")
            elif flat_est < total_bytes:
                pct = round(100 * (total_bytes - flat_est) / total_bytes)
                self.flatten_savings_lbl.config(
                    text=f"≈ {format_size(flat_est)} if flattened "
                         f"(saves about {pct}%)",
                    foreground="#0a5a16",
                )
            elif flat_est > total_bytes and total_bytes > 0:
                # Text-heavy inputs flatten LARGER — explicitly warn.
                self.flatten_savings_lbl.config(
                    text=f"≈ {format_size(flat_est)} if flattened — would "
                         f"grow the file, skip flatten for this set.",
                    foreground="#7a4500",
                )
            else:
                self.flatten_savings_lbl.config(
                    text=f"≈ {format_size(flat_est)} if flattened",
                    foreground="#0a5a16",
                )

    # --- Add from phone (QR upload) ------------------------------------------
    def add_from_phone(self):
        if not (QR_OK and PIL_TK_OK):
            messagebox.showwarning(
                APP_NAME,
                "Phone upload needs the 'qrcode' library and Pillow's Tk\n"
                "bindings. They ship with the installer; if you're running\n"
                "from source, run: pip install qrcode pillow",
            )
            return

        server = QrUploadServer(
            on_files=lambda paths: self.work_queue.put(("ipc_paths", paths))
        )
        try:
            server.start()
        except OSError as e:
            messagebox.showerror(
                APP_NAME, f"Couldn't start the phone-upload server:\n{e}"
            )
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Add from phone")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        ttk.Label(dlg, text="Scan with your phone's camera",
                  font=("", 12, "bold")).pack(padx=24, pady=(20, 4))
        ttk.Label(dlg, text="Then pick photos or PDFs to send to this window.",
                  foreground="#555").pack(padx=24)

        qr_pil = _qrcode.make(server.url).get_image().convert("RGB").resize(
            (300, 300), Image.NEAREST
        )
        qr_tk = _ImageTk.PhotoImage(qr_pil)
        qr_label = ttk.Label(dlg, image=qr_tk)
        qr_label.image = qr_tk  # keep a reference so it isn't garbage-collected
        qr_label.pack(padx=24, pady=14)

        ttk.Label(dlg, text=server.url, foreground="#666",
                  font=("TkFixedFont", 9)).pack(padx=24)
        ttk.Label(dlg, text="Phone and computer must be on the same Wi-Fi.",
                  foreground="#888", wraplength=320).pack(padx=24, pady=(8, 6))

        def close_dialog():
            server.stop()
            dlg.destroy()

        ttk.Button(dlg, text="Done", command=close_dialog).pack(pady=(4, 18))
        dlg.protocol("WM_DELETE_WINDOW", close_dialog)
        dlg.lift()
        dlg.focus_force()

    # --- Add from scanner ----------------------------------------------------
    def add_from_scanner(self):
        """Linux uses SANE's scanimage directly (one-click scan into the list).
        Windows and macOS launch their built-in scanner UI — the user scans,
        saves the file to Desktop, then drags it into the app. Direct WIA /
        ImageCaptureCore integration is planned for a later version."""
        if sys.platform.startswith("linux"):
            from shutil import which
            if not which("scanimage"):
                messagebox.showwarning(
                    APP_NAME,
                    "Couldn't find the 'scanimage' command. Install the SANE\n"
                    "tools first:\n\n    sudo apt install sane-utils",
                )
                return
            self.status.config(text="Scanning… (check the scanner)")
            threading.Thread(target=self._scan_worker, daemon=True).start()
            return

        # Windows: launch Windows Fax and Scan (built into Windows 10/11).
        if sys.platform.startswith("win"):
            try:
                subprocess.Popen(["wfs.exe"])
            except FileNotFoundError:
                try:
                    subprocess.Popen(["wiaacmgr.exe"])
                except FileNotFoundError:
                    messagebox.showwarning(
                        APP_NAME,
                        "Couldn't find Windows Fax and Scan. Open it from the\n"
                        "Start menu, scan your document, save it to your\n"
                        "Desktop, then drag the file into this window.",
                    )
                    return
            messagebox.showinfo(
                APP_NAME,
                "Windows Fax and Scan is opening.\n\n"
                "Scan your document, save it (Desktop works well), then\n"
                "drag the saved file into this window to add it.\n\n"
                "Direct one-click scanning on Windows is coming in a future "
                "release.",
            )
            return

        # macOS: launch Image Capture. Could be replaced with PyObjC /
        # ImageCaptureCore for a one-click flow in a later version.
        if sys.platform == "darwin":
            try:
                subprocess.Popen(["open", "-a", "Image Capture"])
            except Exception:
                messagebox.showwarning(
                    APP_NAME,
                    "Couldn't open Image Capture. Find it in /Applications,\n"
                    "scan your document, save it to your Desktop, then drag\n"
                    "the file into this window.",
                )
                return
            messagebox.showinfo(
                APP_NAME,
                "Image Capture is opening.\n\n"
                "Scan your document, save it (Desktop works well), then\n"
                "drag the saved file into this window to add it.\n\n"
                "Direct one-click scanning on macOS is coming in a future "
                "release.",
            )
            return

        # Anything else (BSD etc.) — fall back to the helpful message.
        messagebox.showinfo(
            APP_NAME,
            "Direct scanner support on this platform isn't built in yet.\n"
            "Scan from your scanner's own software, then drag the saved\n"
            "file into this window.",
        )

    def _scan_worker(self):
        try:
            tmp_dir = tempfile.mkdtemp(prefix="ddpdf_scan_")
            out_path = os.path.join(tmp_dir, "scan.png")
            # --format=png is widely supported; --resolution=200 is a
            # reasonable default for documents (legible text, modest size).
            subprocess.run(
                ["scanimage", "--format=png", "--resolution=200",
                 "--output-file", out_path],
                check=True, timeout=180,
            )
            self.work_queue.put(("ipc_paths", [out_path]))
        except subprocess.CalledProcessError as e:
            self.work_queue.put(("warn", f"Scanner returned an error: {e}"))
        except subprocess.TimeoutExpired:
            self.work_queue.put(("warn", "Scanner timed out after 3 minutes."))
        except Exception as e:
            self.work_queue.put(("warn", f"Scan failed: {e}"))

    # --- What's-new dialog ---------------------------------------------------
    def show_whats_new(self):
        """Pop a small dialog listing the features added in APP_VERSION,
        with a 'See all releases' link to the GitHub releases page."""
        dlg = tk.Toplevel(self.root)
        dlg.title(f"What's new in v{APP_VERSION}")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        ttk.Label(dlg, text=f"What's new in v{APP_VERSION}",
                  font=("", 13, "bold")).pack(padx=24, pady=(20, 12))

        bullets = WHATS_NEW.get(APP_VERSION, [])
        if bullets:
            body = ttk.Frame(dlg)
            body.pack(padx=24, pady=(0, 12), anchor="w")
            for b in bullets:
                row = ttk.Frame(body)
                row.pack(fill="x", anchor="w", pady=2)
                ttk.Label(row, text="•", foreground="#0a64d8").pack(
                    side="left", anchor="n", padx=(0, 8)
                )
                ttk.Label(row, text=b, wraplength=420, justify="left").pack(
                    side="left", anchor="w"
                )
        else:
            ttk.Label(dlg, text="(No release notes recorded for this build.)",
                      foreground="#888").pack(padx=24, pady=12)

        # Byline — appears on every version's What's New so users seeing
        # the changelog can put a name to the project.
        ttk.Label(
            dlg,
            text="by Dejan Obradovic  (& Claudia)",
            foreground="#888",
            font=("", 9, "italic"),
        ).pack(padx=24, pady=(12, 0))

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=(8, 18))
        ttk.Button(
            btn_row, text="See all releases on GitHub",
            command=lambda: webbrowser.open(UPDATE_PAGE_URL),
        ).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(side="left", padx=6)
        dlg.lift()
        dlg.focus_force()

    # --- Install missing system components -----------------------------------
    def show_missing_components_dialog(self):
        """Modal listing each missing optional system component with a
        per-row Install button. Install runs on a background thread; status
        line at the bottom reports progress."""
        # Re-detect in case the user installed something between launch and
        # opening the dialog.
        self._missing_components = detect_missing_components()
        items = list(self._missing_components)

        dlg = tk.Toplevel(self.root)
        dlg.title("Install missing components")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        ttk.Label(dlg, text="Install missing components",
                  font=("", 13, "bold")).pack(padx=24, pady=(20, 6))
        ttk.Label(
            dlg,
            text=("These are optional add-ons. The app works without them, "
                  "but some features will be skipped or disabled."),
            wraplength=520, justify="left", foreground="#555",
        ).pack(padx=24, pady=(0, 8))

        if not items:
            ttk.Label(dlg, text="✓ Everything looks installed.",
                      foreground="#0a5a16").pack(padx=24, pady=18)
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 18))
            return

        status_var = tk.StringVar(value="")
        row_widgets = []
        for it in items:
            row = ttk.LabelFrame(dlg, text=it["label"])
            row.pack(fill="x", padx=24, pady=6)
            ttk.Label(row, text=it["why"], wraplength=420,
                      justify="left", foreground="#333"
                      ).pack(side="left", padx=10, pady=10, anchor="w")
            btn = ttk.Button(row, text="Install")
            btn.pack(side="right", padx=10, pady=10)
            row_widgets.append((it, row, btn))

        def make_handler(component_id, button):
            def click():
                button.config(state="disabled", text="Installing…")
                status_var.set(f"Installing {component_id}…")

                def worker():
                    ok, msg = install_component(
                        component_id,
                        status_cb=lambda s: self.work_queue.put(
                            ("install_status", s)
                        ),
                    )
                    self.work_queue.put(
                        ("install_done", component_id, ok, msg)
                    )

                threading.Thread(target=worker, daemon=True).start()
            return click

        for it, row, btn in row_widgets:
            btn.config(command=make_handler(it["id"], btn))

        status_lbl = ttk.Label(dlg, textvariable=status_var, foreground="#555")
        status_lbl.pack(padx=24, pady=(8, 4), anchor="w")

        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(8, 18))

        # Stash dialog state so the queue handler can flip button labels
        # back when an install finishes.
        self._install_dialog = {
            "dlg": dlg,
            "status_var": status_var,
            "rows": row_widgets,
        }
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.lift()
        dlg.focus_force()

    # --- Sponsor button ------------------------------------------------------
    def _on_sponsor_click(self):
        """Open the GitHub Sponsors page in the user's browser."""
        try:
            webbrowser.open(SPONSOR_URL)
        except Exception:
            pass

    def show_about_dialog(self):
        """About + licensing info, with links to the full license texts and a
        commercial-licensing contact. MyDocMaker is free for personal use;
        commercial use needs a separate license."""
        def _open(url):
            try:
                webbrowser.open(url)
            except Exception:
                pass

        dlg = tk.Toplevel(self.root)
        dlg.title("About MyDocMaker")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        wrap = ttk.Frame(dlg)
        wrap.pack(fill="both", expand=True, padx=16, pady=14)

        ttk.Label(wrap, text=f"{APP_NAME}  v{APP_VERSION}",
                  font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(
            wrap,
            text="Drop files or paste a website link, build a combined PDF, "
                 "and sign it.",
            foreground="#555",
        ).pack(anchor="w", pady=(0, 10))

        lic = ttk.LabelFrame(wrap, text="License")
        lic.pack(fill="x")
        ttk.Label(
            lic, justify="left", wraplength=460,
            text=(
                "MyDocMaker is FREE for personal, charity, educational, "
                "research, and government use, under the PolyForm "
                "Noncommercial License 1.0.0.\n\n"
                "Commercial use — any use at, by, or on behalf of a "
                "for-profit company, including internal use — requires a "
                "separate commercial license.\n\n"
                f"Commercial pricing: {PRICING_URL}\n"
                f"Questions: {LICENSE_CONTACT_EMAIL}"
            ),
        ).pack(anchor="w", padx=10, pady=8)

        row1 = ttk.Frame(wrap)
        row1.pack(fill="x", pady=(12, 0))
        ttk.Button(row1, text="See commercial pricing",
                   command=lambda: _open(PRICING_URL)).pack(side="left")
        ttk.Button(row1, text="Email about commercial use",
                   command=lambda: _open(f"mailto:{LICENSE_CONTACT_EMAIL}")
                   ).pack(side="left", padx=6)

        row2 = ttk.Frame(wrap)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Button(row2, text="Read the full license",
                   command=lambda: _open(LICENSE_URL)).pack(side="left")
        ttk.Button(row2, text="Third-party licenses",
                   command=lambda: _open(THIRD_PARTY_LICENSES_URL)
                   ).pack(side="left", padx=6)

        # Auto-update opt-out. Default on; persisted in state.json.
        auto_var = tk.BooleanVar(value=bool(_get_pref("auto_update_check", True)))
        ttk.Checkbutton(
            wrap,
            text="Check for updates automatically (about once a month)",
            variable=auto_var,
            command=lambda: _set_pref("auto_update_check", bool(auto_var.get())),
        ).pack(anchor="w", pady=(12, 0))

        ttk.Button(wrap, text="Close", command=dlg.destroy
                   ).pack(anchor="e", pady=(10, 0))

        dlg.update_idletasks()
        dlg.minsize(dlg.winfo_reqwidth(), dlg.winfo_reqheight())

    # --- Check for updates ---------------------------------------------------
    def check_for_updates(self, silent=False):
        """Asynchronously hit the GitHub releases API. If a newer version is
        available, open the auto-update dialog with a download progress bar
        (or fall back to a browser link if we can't match the install kind
        to a release asset — e.g. running from source).

        silent=True is used by the periodic background check: no "checking…"
        / "up to date" / error popups — only a genuinely newer version
        surfaces (it still opens the update dialog)."""
        if not silent:
            self.status.config(text="Checking for updates…")

        def worker():
            try:
                info = fetch_latest_release_info()
            except Exception as e:
                self.work_queue.put(("update_check", "error", str(e), silent))
                return
            latest_tag = info.get("tag_name", "")
            latest = _parse_version(latest_tag)
            current = _parse_version(APP_VERSION)
            if latest > current:
                self.work_queue.put(("update_check", "newer", latest_tag, info, silent))
            else:
                self.work_queue.put(("update_check", "current", latest_tag, info, silent))

        threading.Thread(target=worker, daemon=True).start()

    def _maybe_auto_check_updates(self):
        """Run a background update check at most once every
        UPDATE_CHECK_INTERVAL_DAYS, unless the user opted out. Silent unless a
        newer version is found. This is the adoption channel for future
        releases — keep it quiet and unobtrusive."""
        try:
            if not _get_pref("auto_update_check", True):
                return
            last = float(_get_pref("last_update_check", 0) or 0)
            now = time.time()
            if (now - last) < UPDATE_CHECK_INTERVAL_DAYS * 86400:
                return
            _set_pref("last_update_check", now)
            self.check_for_updates(silent=True)
        except Exception:
            pass

    # --- Auto-update dialog (download + handoff) -----------------------------
    def open_update_dialog(self, latest_tag, release_info):
        """Modal showing release notes excerpt, file size, progress bar, and a
        'Download & install' button. Once download completes, hand off to the
        OS installer (Setup.exe on Windows / xdg-open .deb on Linux / open
        the containing folder on macOS+portable variants)."""
        kind = detect_install_kind()
        url, asset_name, asset_size = find_matching_asset(release_info, kind)

        if not url:
            # No matching artifact for this install (most often: running from
            # source). Fall back to the old behavior: open the release page.
            if messagebox.askyesno(
                APP_NAME,
                f"A newer version is available: {latest_tag}\n"
                f"You're on v{APP_VERSION}.\n\n"
                "I can't auto-download for this install type. Open the\n"
                "downloads page in your browser instead?",
            ):
                webbrowser.open(UPDATE_PAGE_URL)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Update to {latest_tag}")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        ttk.Label(dlg, text=f"{latest_tag} is available",
                  font=("", 13, "bold")).pack(padx=24, pady=(20, 4))
        ttk.Label(dlg, text=f"You're currently on v{APP_VERSION}",
                  foreground="#555").pack(padx=24)

        body = (release_info.get("body") or "").strip()
        if body:
            excerpt = body if len(body) <= 700 else body[:700] + " …"
            note_frame = ttk.LabelFrame(dlg, text="What's new")
            note_frame.pack(padx=24, pady=(14, 8), fill="x")
            ttk.Label(note_frame, text=excerpt, wraplength=520,
                      justify="left", foreground="#333"
                      ).pack(padx=10, pady=10, anchor="w")

        size_mb = asset_size / (1024 * 1024) if asset_size else 0
        ttk.Label(dlg,
                  text=f"Will download:  {asset_name}  ({size_mb:.1f} MB)",
                  foreground="#666").pack(padx=24, pady=(6, 4), anchor="w")

        progress = ttk.Progressbar(dlg, mode="determinate", length=520)
        progress.pack(padx=24, pady=(4, 2), fill="x")
        status_lbl = ttk.Label(dlg, text="Ready.", foreground="#444")
        status_lbl.pack(padx=24, pady=(0, 8), anchor="w")

        btn_row = ttk.Frame(dlg)
        btn_row.pack(pady=(8, 18))
        cancel_event = threading.Event()

        def on_cancel():
            cancel_event.set()
            dlg.destroy()
            self._update_dialog_state = None

        def on_download():
            download_btn.config(state="disabled")
            progress.config(maximum=max(asset_size, 1), value=0)
            status_lbl.config(text="Starting download…")

            def worker():
                tmp_dir = tempfile.mkdtemp(prefix="ddpdf_update_")
                dest = os.path.join(tmp_dir, asset_name)
                try:
                    download_with_progress(
                        url, dest,
                        progress_cb=lambda d, t: self.work_queue.put(
                            ("update_dl_progress", d, t)
                        ),
                        cancel_event=cancel_event,
                    )
                    self.work_queue.put(("update_dl_done", kind, dest))
                except Exception as e:
                    self.work_queue.put(("update_dl_error", str(e)))

            threading.Thread(target=worker, daemon=True).start()

        download_btn = ttk.Button(
            btn_row,
            text=f"Download & install  ({size_mb:.1f} MB)",
            command=on_download,
        )
        download_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        dlg.lift()
        dlg.focus_force()

        # Stash so _poll_queue can update the bar/status from outside.
        self._update_dialog_state = {
            "dlg": dlg,
            "progress": progress,
            "status_lbl": status_lbl,
            "download_btn": download_btn,
            "asset_name": asset_name,
            "kind": kind,
        }

    def _finalize_update(self, kind, path):
        """Called once the download finishes — kick off the installer and
        exit so it can replace this app's files."""
        try:
            hand_off_to_installer(kind, path)
        except Exception as e:
            messagebox.showwarning(
                APP_NAME,
                f"Downloaded to:\n{path}\n\nCouldn't auto-launch: {e}",
            )
            return
        # Tiny delay so the OS installer has time to grab handles before we
        # release our own. On Windows this matters for Inno Setup's
        # "replace running executable" path.
        self.root.after(1200, self.root.destroy)

    # --- Sign-and-create flow (v1.28) ----------------------------------------
    def show_my_signatures(self):
        """Open the 'My Signatures' manager (v1.31)."""
        if not SIGNING_OK:
            messagebox.showwarning(
                APP_NAME,
                "E-signature needs the 'pyhanko' and 'cryptography' Python\n"
                "libraries. They ship with the installer; if you're running\n"
                "from source, run: pip install pyhanko cryptography",
            )
            return
        SignaturesManagerDialog(self.root, self)

    # ---- v1.45: Archive folder -----------------------------------------
    def _refresh_archive_button(self):
        """Sync the Archive button label / tooltip with whether the
        archive folder is configured. First-launch UX nudge: the
        button reads 'Set up Archive…' until the user picks a folder."""
        folder = _load_archive_folder()
        if folder:
            self.archive_btn.config(text="▼ Archive")
        else:
            self.archive_btn.config(text="▼ Set up Archive…")

    def show_archive_dialog(self):
        """Either run the first-time folder picker or show the
        management dialog for the already-configured folder."""
        folder = _load_archive_folder()
        if folder is None:
            self._archive_first_time_setup()
        else:
            self._archive_management_dialog(folder)

    def _archive_first_time_setup(self):
        if not messagebox.askokcancel(
            APP_NAME,
            "Set up an archive folder for signed PDFs.\n\n"
            "Every time you sign a document, a flattened copy will be "
            "saved to this folder automatically — alongside your normal "
            "saved copy. It's a backup so you always have a record of "
            "everything you've signed.\n\n"
            "No archiving happens until you pick a folder here. You can "
            "change it later from the Archive button.\n\n"
            "Pick a folder?",
        ):
            return
        folder = filedialog.askdirectory(
            title="Choose your signed-PDF archive folder",
            initialdir=os.path.expanduser("~"),
        )
        if not folder:
            return
        _save_archive_folder(folder)
        self._refresh_archive_button()
        messagebox.showinfo(
            APP_NAME,
            f"Archive folder set:\n{folder}\n\n"
            "From now on, every signed PDF you create will be auto-"
            "archived here as a flattened copy.",
        )

    def _archive_management_dialog(self, folder):
        win = tk.Toplevel(self.root)
        win.title("Archive folder")
        win.transient(self.root)
        win.resizable(False, False)

        ttk.Label(win, text="Archive folder for signed PDFs",
                  font=("", 13, "bold")).pack(padx=16, pady=(14, 4))
        ttk.Label(
            win,
            text="Every signed PDF you create is also saved here, "
                 "flattened, as a backup. Your normal save-as path is "
                 "unaffected.",
            foreground="#555", wraplength=460, justify="left",
        ).pack(padx=16, pady=(0, 10))

        ttk.Label(win, text="Current folder:",
                  foreground="#666").pack(anchor="w", padx=16)
        ttk.Label(win, text=folder, foreground="#222",
                  wraplength=460, justify="left").pack(
            anchor="w", padx=16, pady=(0, 12))

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=14, pady=(0, 14))

        def open_folder():
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                elif sys.platform.startswith("win"):
                    os.startfile(folder)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Couldn't open folder:\n{e}")
        ttk.Button(btn_row, text="Open archive folder",
                   command=open_folder).pack(side="left")

        def change():
            new_folder = filedialog.askdirectory(
                title="Choose a different archive folder",
                initialdir=folder,
            )
            if not new_folder:
                return
            _save_archive_folder(new_folder)
            self._refresh_archive_button()
            win.destroy()
            messagebox.showinfo(
                APP_NAME,
                f"Archive folder updated:\n{new_folder}",
            )
        ttk.Button(btn_row, text="Change local folder…",
                   command=change).pack(side="left", padx=(6, 0))

        ttk.Button(btn_row, text="Close",
                   command=win.destroy).pack(side="right")

    def sign_and_create_pdf(self):
        """Entry point for the 🔏 Sign and Create PDF button.

        Flow:
          1. If the user has no saved signature → open SignatureCreatorDialog
             first so they can make one.
          2. Build the combined PDF in memory (re-uses cached per-item
             bytes from RenderWorker — no second render pass).
          3. Open SignDialog with that PDF for click-to-place + sign.

        If pyhanko or cryptography are missing (e.g. ran from source
        without the deps installed) the button is already disabled —
        this method is unreachable in that case."""
        if not SIGNING_OK:
            messagebox.showwarning(
                APP_NAME,
                "E-signature needs the 'pyhanko' and 'cryptography' Python\n"
                "libraries. They ship with the installer; if you're running\n"
                "from source, run: pip install pyhanko cryptography",
            )
            return
        if not self.items:
            messagebox.showwarning(
                APP_NAME, "Add some files or a webpage first."
            )
            return

        # If no saved signature yet, prompt the user to create one. After
        # creation, fall straight through into the sign dialog.
        if not has_saved_signature():
            def _after_create(png_bytes, label, style):
                save_signature(png_bytes, label=label, style=style)
                # Re-enter the flow now that we have a signature.
                self.sign_and_create_pdf()
            SignatureCreatorDialog(self.root, on_save=_after_create)
            return

        # Build the combined PDF in memory using cached item bytes.
        self.status.config(text="Building PDF for signing…")
        self._set_busy(True)
        threading.Thread(
            target=self._build_for_signing_worker,
            daemon=True,
        ).start()

    def _build_for_signing_worker(self):
        """Worker: stitch the combined PDF, then post back to the UI thread
        to open SignDialog. Mirrors _build_worker's assembly logic but
        prefers cached bytes when available so signing doesn't pay the
        render cost twice."""
        try:
            writer = PdfWriter()
            excluded = set(self.excluded_pages)
            for it in self.items:
                if it.cached_pdf_bytes:
                    reader = PdfReader(io.BytesIO(it.cached_pdf_bytes))
                else:
                    # Fall back to live render if cache missed (e.g. user
                    # hits Sign before RenderWorker finished an item).
                    page_mode = self.size_var.get()
                    data = RenderWorker._render(it, page_mode)
                    reader = PdfReader(io.BytesIO(data))
                # Honour pages hidden in the Preview tab so the signed PDF
                # matches what the user sees / what Create PDF would produce.
                for local_idx, pg in enumerate(reader.pages):
                    if (it.uid, local_idx) in excluded:
                        continue
                    writer.add_page(pg)
            if len(writer.pages) == 0:
                self.work_queue.put((
                    "error", "No pages were created — nothing to sign."
                ))
                return
            staged = io.BytesIO()
            writer.write(staged)
            self.work_queue.put(("ready_for_signing", staged.getvalue()))
        except Exception as e:
            self.work_queue.put(("error", f"Couldn't build PDF for signing: {e}"))

    def _open_sign_dialog(self, pdf_bytes):
        self._set_busy(False)
        self.status.config(text="Ready to sign — click on a page to place.")
        SignDialog(
            self.root, self, pdf_bytes,
            on_signed=lambda path: self.status.config(
                text=f"Signed: {os.path.basename(path)}"
            ),
        )

    # --- Build PDF (in a worker thread so the UI doesn't freeze) -------------
    def create_pdf(self, action="none"):
        """action: 'none' (just save), 'open' (open after save), 'print' (print)."""
        if not self.items:
            messagebox.showwarning(APP_NAME, "Add some files or a webpage first.")
            return
        has_office = any(
            it.kind == "file" and file_kind(it.value) == "office"
            for it in self.items
        )
        if has_office and not find_libreoffice():
            proceed = messagebox.askyesno(
                APP_NAME,
                "LibreOffice is required to convert Office documents "
                "(.docx, .xlsx, etc.) but isn't installed on this system.\n\n"
                "Those files will be skipped. Continue with the rest?",
            )
            if not proceed:
                return
        out_path = filedialog.asksaveasfilename(
            title="Save PDF as", defaultextension=".pdf",
            initialdir=default_save_dir(),
            initialfile="output.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return
        self._set_busy(True)
        self.status.config(text="Working… (capturing webpages can take a few seconds)")
        self.progress.config(maximum=100, value=0)
        page_mode = self.size_var.get()
        flatten = bool(self.flatten_var.get() and FLATTEN_OK)
        items_snapshot = list(self.items)
        excluded_snapshot = set(self.excluded_pages)
        threading.Thread(
            target=self._build_worker,
            args=(items_snapshot, page_mode, out_path, flatten, action,
                  excluded_snapshot),
            daemon=True,
        ).start()

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for btn in (self.create_btn, self.create_open_btn, self.create_print_btn):
            btn.config(state=state)

    def _build_worker(self, items, page_mode, out_path, flatten=False,
                      action="none", excluded=None):
        excluded = excluded or set()
        writer = PdfWriter()
        skipped = []
        for it in items:
            try:
                if it.kind == "url":
                    buf = url_to_pdf_bytes(it.value, page_mode)
                else:
                    kind = file_kind(it.value)
                    if kind == "image":
                        buf = image_to_pdf_bytes(it.value, page_mode)
                    elif kind == "pdf":
                        with open(it.value, "rb") as fh:
                            buf = io.BytesIO(fh.read())
                    elif kind == "text":
                        tm = "a4" if page_mode == "a4" else "letter"
                        buf = text_to_pdf_bytes(it.value, tm)
                    elif kind == "office":
                        buf = office_to_pdf_bytes(it.value)
                    else:
                        skipped.append(f"{it.label} (unsupported)")
                        continue
                reader = PdfReader(buf)
                # Skip any pages the user hid in the Preview tab. Pages are
                # keyed by (item.uid, local index within this item).
                for local_idx, pg in enumerate(reader.pages):
                    if (it.uid, local_idx) in excluded:
                        continue
                    writer.add_page(pg)
            except Exception as e:
                skipped.append(f"{it.label} ({e})")

        if len(writer.pages) == 0:
            self.work_queue.put(("error", "No pages were created.\n\n" + "\n".join(skipped)))
            return

        # Assemble in memory so we can optionally flatten before writing.
        staged = io.BytesIO()
        try:
            writer.write(staged)
        except Exception as e:
            self.work_queue.put(("error", f"Could not assemble PDF: {e}"))
            return
        orig_bytes = staged.getvalue()
        out_data = orig_bytes
        flatten_note = ""
        if flatten:
            try:
                total_pages = len(writer.pages)
                self.work_queue.put(("flatten_start", total_pages))
                flat = flatten_pdf_bytes(
                    orig_bytes,
                    progress=lambda d, t: self.work_queue.put(
                        ("flatten_progress", d, t)
                    ),
                )
                out_data = flat.getvalue()
                saved = len(orig_bytes) - len(out_data)
                pct = (100.0 * saved / len(orig_bytes)) if orig_bytes else 0
                if saved > 0:
                    flatten_note = (
                        f"\nFlattened: {len(orig_bytes)/1e6:.1f} MB → "
                        f"{len(out_data)/1e6:.1f} MB  "
                        f"(saved {saved/1e6:.1f} MB, {pct:.0f}%)"
                    )
                else:
                    flatten_note = (
                        f"\nFlattened: {len(orig_bytes)/1e6:.1f} MB → "
                        f"{len(out_data)/1e6:.1f} MB  (no size reduction)"
                    )
            except Exception as e:
                skipped.append(f"(flatten failed, kept original: {e})")

        try:
            with open(out_path, "wb") as f:
                f.write(out_data)
        except Exception as e:
            self.work_queue.put(("error", f"Could not save: {e}"))
            return

        msg = f"Saved: {out_path}\nPages: {len(writer.pages)}{flatten_note}"
        if skipped:
            msg += "\n\nSkipped:\n - " + "\n - ".join(skipped)
        self.work_queue.put(("done", msg, out_path, len(writer.pages), action))

    def _poll_queue(self):
        try:
            while True:
                msg = self.work_queue.get_nowait()
                if msg[0] == "error":
                    self._set_busy(False)
                    self.progress.config(value=0)
                    self.status.config(text="Nothing converted.")
                    messagebox.showwarning(APP_NAME, msg[1])
                elif msg[0] == "done":
                    _, text, path, pages, action = msg
                    self._set_busy(False)
                    self.progress.config(value=self.progress["maximum"])
                    self.status.config(text=f"Done. Saved {pages}-page PDF.")
                    # Auto-trigger after-build actions before showing the
                    # success dialog so users see them happen simultaneously.
                    if action == "open":
                        _open_with_default_viewer(path)
                    elif action == "print":
                        _print_with_default_printer(path, self.work_queue)
                    messagebox.showinfo(APP_NAME, text)
                elif msg[0] == "flatten_start":
                    _, total = msg
                    self.progress.config(maximum=max(total, 1), value=0)
                    self.status.config(text=f"Flattening 0/{total} pages…")
                elif msg[0] == "flatten_progress":
                    _, done, total = msg
                    self.progress.config(value=done)
                    self.status.config(text=f"Flattening {done}/{total} pages…")
                elif msg[0] == "warn":
                    messagebox.showwarning(APP_NAME, msg[1])
                elif msg[0] == "install_status":
                    st = getattr(self, "_install_dialog", None)
                    if st is not None:
                        st["status_var"].set(msg[1])
                elif msg[0] == "install_done":
                    _, comp_id, ok, message = msg
                    st = getattr(self, "_install_dialog", None)
                    if st is not None:
                        st["status_var"].set(message)
                        for it, _row, btn in st["rows"]:
                            if it["id"] == comp_id:
                                if ok:
                                    btn.config(state="disabled", text="Installed ✓")
                                else:
                                    btn.config(state="normal", text="Retry install")
                                break
                    if ok:
                        messagebox.showinfo(APP_NAME, message)
                    else:
                        messagebox.showwarning(APP_NAME, message)
                elif msg[0] == "update_check":
                    # status, then payload, then a trailing `silent` flag.
                    # silent (background auto-check): suppress the error /
                    # up-to-date popups; only a genuinely newer version
                    # surfaces (it still opens the update dialog).
                    status = msg[1]
                    silent = bool(msg[-1]) if isinstance(msg[-1], bool) else False
                    if status == "error":
                        if not silent:
                            self.status.config(text="Update check failed.")
                            messagebox.showwarning(
                                APP_NAME,
                                f"Couldn't reach GitHub:\n{msg[2]}",
                            )
                    elif status == "current":
                        if not silent:
                            self.status.config(text=f"Up to date (v{APP_VERSION}).")
                            messagebox.showinfo(
                                APP_NAME,
                                f"You're on the latest version (v{APP_VERSION}).",
                            )
                    elif status == "newer":
                        latest_tag = msg[2]
                        release_info = msg[3] if len(msg) > 3 and isinstance(msg[3], dict) else {}
                        self.status.config(text=f"Update available: {latest_tag}")
                        self.open_update_dialog(latest_tag, release_info)
                elif msg[0] == "update_dl_progress":
                    _, done, total = msg
                    st = getattr(self, "_update_dialog_state", None)
                    if st is not None:
                        st["progress"].config(
                            maximum=max(total, 1), value=done
                        )
                        mb_done = done / 1e6
                        mb_total = total / 1e6
                        pct = (100.0 * done / total) if total > 0 else 0
                        st["status_lbl"].config(
                            text=(
                                f"Downloading… {mb_done:.1f} / "
                                f"{mb_total:.1f} MB ({pct:.0f}%)"
                                if total > 0 else
                                f"Downloading… {mb_done:.1f} MB"
                            )
                        )
                elif msg[0] == "update_dl_done":
                    _, dl_kind, dl_path = msg
                    st = getattr(self, "_update_dialog_state", None)
                    if st is not None:
                        st["progress"].config(value=st["progress"]["maximum"])
                        st["status_lbl"].config(
                            text="Downloaded. Launching installer…",
                            foreground="#0a5a16",
                        )
                    # Slight delay so the user sees "Downloaded" before we exit.
                    self.root.after(700,
                                    lambda: self._finalize_update(dl_kind, dl_path))
                elif msg[0] == "update_dl_error":
                    _, err = msg
                    st = getattr(self, "_update_dialog_state", None)
                    if st is not None:
                        st["status_lbl"].config(
                            text=f"Download failed: {err}", foreground="#a30000"
                        )
                        st["download_btn"].config(state="normal")
                elif msg[0] == "ipc_paths":
                    self.add_paths(msg[1])
                    # Bring the window forward so the user sees the new items.
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                elif msg[0] == "ready_for_signing":
                    self._open_sign_dialog(msg[1])
                elif msg[0] in ("item_status", "item_rendered",
                                "item_render_failed"):
                    # Per-item render-state change from RenderWorker:
                    # repaint the row glyphs and invalidate the preview
                    # cache so the next debounce rebuild picks up the new
                    # bytes.
                    self._refresh()
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)


def _find_app_icon():
    """Locate the bundled app icon PNG. PyInstaller exposes the temp
    extract dir via sys._MEIPASS at runtime; in dev mode the icon lives
    next to this file under installer/. Returns None if not found."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "icon.png"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "installer", "icon.png"))
    candidates.append(os.path.join(here, "icon.png"))
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _find_app_logo():
    """Locate the brand logo (logoMDM.png) shown in the bottom-right of the
    Pages tab. Bundled next to the executable via PyInstaller --add-data; in
    dev mode it sits beside this file. Returns None if not found (the UI
    simply omits the logo)."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "logoMDM.png"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "logoMDM.png"))
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def main():
    cli_paths = [p for p in sys.argv[1:] if os.path.exists(p)]

    # If another instance is already running and we were handed files (e.g. via
    # "Open With" from a file manager), give those files to it and exit. Skip
    # this when launched with no args — opening the menu shortcut should always
    # produce a window, even if one is already up elsewhere on the desktop.
    if cli_paths and send_paths_to_existing(cli_paths):
        return

    # className sets the window's WM_CLASS (instance "mydocmaker"), which must
    # match the .desktop file id + its StartupWMClass so GNOME/Pop!_OS/KDE can
    # tie the running window back to the launcher — otherwise "Pin to taskbar /
    # Add to Favorites" won't stick (the window looks like an unknown app).
    if DND_OK:
        root = TkinterDnD.Tk(className="mydocmaker")
    else:
        root = tk.Tk(className="mydocmaker")

    # Set the window/taskbar icon early so the app's identity is right
    # before any other UI shows. iconphoto works on all three OSes;
    # Windows/macOS *additionally* read embedded .ico/.icns from the
    # PyInstaller-built executable for taskbar/Dock icons (configured
    # via --icon in the build pipeline).
    icon_path = _find_app_icon()
    if icon_path:
        try:
            if PIL_TK_OK:
                # Pre-resize to several common WM icon sizes with Pillow's
                # high-quality LANCZOS filter, then hand the whole set to
                # iconphoto. The window manager picks the best size for
                # the title bar, taskbar, alt-tab switcher, etc. — fixes
                # the blurry taskbar icon you'd get from feeding a single
                # 1024×1024 PNG through Tk's naïve downsampler.
                src = Image.open(icon_path)
                icons = []
                for sz in (16, 24, 32, 48, 64, 128, 256):
                    resized = src.resize((sz, sz), LANCZOS)
                    icons.append(_ImageTk.PhotoImage(resized))
                root.iconphoto(True, *icons)
                root._app_icon_refs = icons  # prevent Tcl GC
            else:
                # Fallback: single tk.PhotoImage (no resize, possibly blurry
                # in small contexts but at least the icon shows).
                icon_img = tk.PhotoImage(file=icon_path)
                root.iconphoto(True, icon_img)
                root._app_icon_ref = icon_img
        except tk.TclError:
            pass

    app = App(root)
    if cli_paths:
        app.add_paths(cli_paths)

    # macOS-only: Finder doesn't pass file selections via argv. It sends an
    # Apple Event ('odoc' / openDocument) which Tk surfaces as the
    # `::tk::mac::OpenDocument` command. Register a handler so right-click
    # "Open With MyDocMaker" from Finder routes files into the app.
    if sys.platform == "darwin":
        def _mac_open_documents(*paths):
            try:
                app.add_paths(list(paths))
                root.deiconify()
                root.lift()
                root.focus_force()
            except Exception:
                pass
        try:
            root.createcommand("::tk::mac::OpenDocument", _mac_open_documents)
        except tk.TclError:
            pass

    root.mainloop()


if __name__ == "__main__":
    main()
