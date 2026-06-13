# Changelog

## v1.47
- **Create-signature dialog defaults to Digital.** Creating a new signature
  now always lands on the Digital (full business stamp) option instead of
  Typed. Editing an existing signature still opens in that signature's own
  mode.
- **Sponsor ♡ button works.** The footer heart now opens
  https://github.com/sponsors/fixmoose — it was previously a no-op.
- **New "About / License" panel** in the footer. MyDocMaker is free for
  personal use under the PolyForm Noncommercial License; commercial use
  requires a separate license. The panel links the commercial-pricing page
  (mydocmaker.com/pricing), a commercial-licensing contact, and the full
  license + third-party license texts. Fixed a stray `License: MIT` note in
  the source header (the project is PolyForm-NC).
- **Automatic update check.** On launch the app now checks GitHub for a newer
  release at most once every 30 days, in the background — silent unless a
  newer version is found, then it offers the existing Download & install
  flow. Opt out anytime via a checkbox in About / License.

## v1.46
- **Signature picker in the Sign dialog** — when you have more than one
  saved signature, choose which one each placed signature uses. Previously
  this was only reachable through a hidden per-window right-click menu, so
  every spot silently used the first signature.
- **Remove individual pages** from the combined document before building —
  including single pages inside multi-page input PDFs — via a per-page
  **Remove** button and a **Restore** control. Honoured by both **Create
  PDF** and the **Sign & Create** flow.
- The **MyDocMaker logo** now appears in the window header.
- **macOS:** fixed the *"MyDocMaker.app is damaged and can't be opened"*
  Gatekeeper error. The `.app` is ad-hoc re-signed after its `Info.plist`
  is finalised and packaged with `ditto`, so the signature stays valid on
  Apple Silicon. README gains an `xattr` quarantine-removal fallback.


## v1.45
- **▼ Archive** button added to the footer (right side, next to
  My Signatures). Click it once to pick a folder where every
  signed PDF gets auto-saved as a **flattened copy** — a backup
  separate from wherever you save the signed file yourself.
- First-time UX: the button reads **"Set up Archive…"** until
  configured, then switches to **"Archive"** (click for a small
  management dialog: open folder / change folder / close).
- Until you pick a folder, nothing is archived — it's strictly
  opt-in. Stored next to your session prefs in
  `~/.config/mydocmaker/state.json` so it persists
  across launches.
- Archived copies are flattened (rasterized) so they're
  self-contained snapshots viewable in any PDF reader, great for
  long-term recordkeeping. The audit JSON sidecar is copied to
  the archive too.

## v1.44
- 🔒 **Signed PDFs are now tamper-protected end-to-end.** Three
  layers of defense:
  1. The signature visual is baked into the **page's content
     stream** (raster overlay via reportlab `merge_page`). Basic
     PDF editors (Foxit, Master PDF) can no longer quietly delete
     the widget annotation and have the visual disappear — the
     visual is part of the page itself, not a removable
     annotation.
  2. A visible Acrobat-style signature widget is **still added
     on top** so Acrobat shows the clickable signature badge and
     the verification panel works as expected.
  3. The first signature on the document **certifies it with
     `MDPPerm.FILL_FORMS`** — Acrobat marks the signature
     "invalid" the moment anyone modifies the page content, while
     still allowing other signers to fill any empty signature
     fields you left for them in Prepare mode.
- New explainer line in the Sign dialog so the user (and the
  recipient) understand the protection model.

## v1.43
- Signature stamp shrunk to **220 × 66 pt** (was 240 × 72) — less
  page real estate, less wasted white space inside.
- Internal padding tightened: text now sits close to the edges of
  the stamp rather than floating in the middle with margins all
  around. The cursive signature image is also `getbbox()`-cropped
  before placement so its actual visible content fills the left
  half — no more transparent padding being included in the scale.
- New **✓ SHA-256 · &lt;timestamp&gt;** badge on the bottom line.
  Communicates the cryptographic protection type AND when the
  document was signed in one compact element. Uses the U+2713
  CHECK MARK (in every system sans-serif), no emoji fonts
  required.
- Long company names and addresses now wrap by **pixel width**
  instead of guessing at character count, so lines never overflow
  the right pane regardless of language or character mix.

## v1.42
- **Fix: long names no longer clipped** in the cursive signature
  image. The renderer (`_render_name_to_png` /
  `_render_type_preview`) used a fixed 140 px font, which made
  names like "Dejan Obradovic" overflow the 960 px canvas and get
  truncated at both edges. Now starts at 140 px and shrinks the
  font in 8 px steps until the full name fits with margin.
- **My Signatures manager preview shows the full composed
  appearance** — signature image + name + company + address + tax
  ID + license + timestamp — same renderer the signed PDF uses.
  Previously it showed only the raw cursive PNG with metadata
  listed as plain text below, which didn't match what the actual
  signed PDF would look like.

## v1.41
- **Bigger preview** in the signature creator: 560 × 200 px
  thumbnail (was 420 × 130). Tighter downsample from the 960 × 288
  composed appearance, so the supporting lines (address, tax,
  license, timestamp) are actually visible in the dialog. v1.40's
  preview was rendering those lines at ~10 px on screen which
  effectively disappeared.
- **Larger fonts** in the appearance composer too: name 42→48,
  company 30→32, caption 26→28, timestamp 24→26 px. On the rendered
  PDF stamp the text now lands at ~12 pt (name), ~8 pt (company),
  ~7 pt (other lines), ~6.5 pt (timestamp) — every line
  comfortably readable.
- Stamp box stays at the v1.40 DocuSign size (240 × 72 pt).

## v1.40
- Signature box right-sized to match real DocuSign stamps.
  **Default is now 240 × 72 pt** (~3.3″ × 1″) — down from
  v1.39's 320 × 100 pt which felt oversized.
- Appearance layout tightened: dropped the redundant
  "Signed by" header (the cursive sig on the left implies
  it), reduced internal padding, packed metadata into
  single-line rows. Name is bold and dominant; company,
  address, tax, license, timestamp stack underneath.
- Same on-page text density and legibility, less wasted
  whitespace, signature stamp is no longer the size of a
  credit card.

## v1.39
- 🔏 **Digital signatures are now actually readable.** The
  default stamp box jumps from 200×60 pt to **320×100 pt** —
  DocuSign-ish proportions. The signature now has real estate on
  the page instead of being postage-stamp sized.
- Composed appearance PNG: now **1280×400** (was 600×180) with
  a **52 px bold name** and 28–36 px supporting text — on-page
  text lands around **8–14 pt**, legible at 100% zoom.
- The auto-rendered cursive name (Digital mode) renders at
  **960×280** with a **140 px font**, so the signature visual
  stays sharp even at 200% zoom in Acrobat.
- Cursive font selection reaches for real script faces across
  all three platforms — Apple Chancery / Snell Roundhand on
  macOS, Monotype Corsiva / Segoe Script on Windows, URW Chancery
  on Linux — and falls back to italic serif only when nothing
  else is installed.

## v1.38
- **Fix:** the chosen signature mode (Digital / Typed / Drawn) is
  now actually persisted with each saved signature. v1.32–v1.37
  set `creator_mode` on the meta dict but `save_signature_record`
  filtered the JSON write by `SIGNATURE_META_FIELDS`, which didn't
  whitelist `creator_mode` — so on disk only `style` survived, and
  on edit the dialog fell back to the inferred default (usually
  Typed for Digital signatures).
- Added `creator_mode` to the whitelist and improved the
  edit-time mode inference so signatures saved before this fix
  open in the right mode (`style == "digital"` → Digital mode).

## v1.37
- 🔏 **Critical fix:** the DocuSign-style stamp now actually
  appears on the signed PDF. v1.36 wired the composed appearance
  through pyhanko's `StaticStampStyle.from_pdf_file` but
  pre-created the signature widget via `append_signature_field` —
  pyhanko silently ignores `stamp_style` when the widget already
  exists. v1.37 lets `PdfSigner` create the field itself via
  `new_field_spec`, which is the only code path that actually
  applies the stamp style.
- Pillow forward-compat: introduced a module-level `LANCZOS`
  constant probed via `Image.Resampling.LANCZOS` with a fallback
  to `Image.LANCZOS` for Pillow ≤ 10. Pillow 11 removed the bare
  `Image.LANCZOS`, which would have broken the bundled build at
  runtime as soon as PyInstaller picked up a newer Pillow.
- Signature preview no longer disappears silently. Any exception
  inside the preview pipeline (font load, PIL resampling,
  appearance compose) now surfaces as a red one-line error in
  the preview area instead of a blank box; full traceback is
  also printed to stderr.

## v1.36
- 🔏 **Critical fix:** signed PDFs now show your **full identity**
  on the visible signature stamp — name, company, address, Tax ID,
  License — not just name + timestamp. Two bugs were stacked:
  1. `sign_pdf_with_appearance_multi` passed `stamp_style=None`
     to pyhanko, so the composed appearance PNG was never used
     and pyhanko fell back to its minimal default "Digitally
     signed by …" text. This bug was latent since v1.29.
  2. The metadata (company, address, etc.) was never passed into
     the appearance composer in the first place.
- v1.36 fixes both: the composed PNG is now wrapped into a
  single-page PDF and applied via `StaticStampStyle.from_pdf_file`,
  and `sign_pdf_with_appearance_multi` accepts a full `signer_meta`
  dict per position.
- 📐 **WYSIWYG preview** in the signature creator. Each of the
  three modes now shows a live preview of **exactly what the
  signed stamp will look like** on the PDF — left half is the
  signature image, right half is the identity + timestamp. Type
  in Digital mode and watch your company / address / license
  appear in the preview in real time.
- Digital mode auto-renders your Name in a cursive script as
  the signature image — no typing or drawing UI in this mode.

## v1.35
- Signature creator: three distinct, **self-contained** signature
  types. No more mixing visual widgets across modes.
  - **Digital** — DocuSign-style. Fill in your business details
    (name, company, address, VAT/EIN/Tax/License); the signature
    image is auto-rendered from your Name in a cursive script.
    There are **no Type or Draw widgets** in this mode — the
    metadata IS the signature. Save button reads "Save digital
    signature."
  - **Typed** — type your name, pick a font style.
  - **Drawn** — draw your signature freehand.
- Internal: `creator_mode == 'create_full'` from v1.31–v1.34 is
  auto-migrated to `'digital'` when editing an existing signature.

## v1.34
- **Fix:** in "Create signature — full details" mode, the dialog
  was stacking BOTH the Type and Draw visual frames + the Details
  fields at once, ballooning the dialog (especially when editing
  an existing signature). Now this mode shows a compact **Type /
  Draw sub-chooser** at the top — pick one visual, fill it in,
  fill in your details, click Save. Only one visual visible at a
  time, so the dialog stays at a reasonable size.

## v1.33
- **Per-mode Save buttons in the signature creator**. Each of the
  three modes now has its own contextual Save button at the bottom
  of that mode's panel:
  - "Create signature" mode → "Save signature with details"
  - "Type your name" mode → "Save typed signature"
  - "Draw your signature" mode → "Save drawn signature"
  Clicking the Save button creates that single signature and
  closes the dialog. No more global Save at the bottom — the
  action is always unambiguous.
- One signature = one type. If you want a different style, create
  another signature via **My Signatures** and use the right-click
  **Sign as** menu in the signing dialog to apply different
  signatures to different windows in the same PDF.

## v1.32
- **My Signatures** button moved to the **bottom-right of the
  footer** — it's a setup-once action so it now sits out of the
  way until you need it.
- 🔏 **Signature creator restructured** into three clear top-level
  options:
  - **Create signature — full details** (best for business and
    legal documents). Visual (typed or drawn) + name, company,
    address, VAT/EIN/Tax/License.
  - **Type your name** — quick cursive signature, just name +
    style.
  - **Draw your signature** — quick drawn signature with **much
    higher rendering quality**: 4× oversampled at canvas time and
    LANCZOS-downsampled, so strokes look polished and smooth on
    the final PDF instead of pixelated.
- **Mode-aware right-click menu** in the signing dialog:
  - **Sign mode** → `Sign as ▸ <your saved signatures>` (as in
    v1.31)
  - **Prepare mode** → `Assign to ▸ Person 1 / Person 2 / …`,
    drawn from a session-local Persons list.
- New **Persons editor** in prepare-for-others mode. Add a name
  and email for each person; that data ends up in the PDF as
  `Signature 2 - Alice Smith <alice@example.com>` so Acrobat's
  signature panel and the on-page placeholder caption identify
  each signer clearly instead of just "For other signer".
- **Per-person colours** on prepare-mode signature windows (amber
  / green / purple / red / blue / cyan, cycling) so the layout
  reads at a glance.

## v1.31
- 🔏 **Multiple saved signatures**. New **My Signatures** button
  (top-right under the Sign row) opens a manager where you can
  create, edit, and delete as many signatures as you want.
- Each signature carries **name, company, address, and
  VAT/EIN/Tax/License** fields. Use this when you sign personally
  AND on behalf of a company, or for different clients.
- Right-click a signature window in the Sign dialog →
  **Sign as ▸ &lt;saved signature&gt;** picks which signature signs
  that window. Each window can be a different signature, so one
  PDF can be signed under multiple identities in a single pass.
- Or leave a window empty: it becomes a clickable signature field
  for someone else to fill in later in Acrobat / Foxit. v1.31 also
  draws a **visible blue dashed rectangle + caption** on the page
  so the recipient can SEE where to sign, not just where a hidden
  widget hit-tests. Fixes "prepare-for-others mode produces a PDF
  with no visible rectangles."
- **Outline-only rectangles** in the Sign dialog — no more fill
  colour covering the page content. Amber outline = will be signed;
  grey dashed outline = empty (for someone else); blue = selected.
- v1.28's single saved signature is **auto-migrated** into the new
  multi-sig store the first time v1.31 launches — your existing
  signature is preserved as the first entry, no action required.
- Deferred to v1.32: resize handles on the canvas, image-upload
  signature method, per-signature certificates (today all sigs
  share one self-signed cert per machine; the appearance + audit
  log already differentiate signer names), Verify dialog.

## v1.30
- Sign dialog **rectangles are now visible** — v1.29's invisible
  boxes were caused by Tk silently ignoring `#RRGGBBAA` alpha
  colors. Switched to opaque RGB fills + 2 px solid outlines.
- **Per-owner color palette**: Person 1 = amber, Person 2 = green,
  Person 3 = purple, Person 4 = red, Person 5 = blue.
- **Big centered label** inside every rectangle:
  `Signature window #N` with `Person #M — page X` subtitle.
- Auto-renumbering: deleting a spot in the middle of the list
  re-numbers the rest with no extra clicks.
- **Click position = center of stamp**. v1.29 anchored the
  top-left at the cursor — surprising.
- **Simpler mouse model**: left-click empty = place new;
  left-click spot = select; left-drag = move. No more
  right-click-then-click for moves.
- **Right-click context menu** on a stamp: *Assign to Person N*
  (sub-menu), *Size* presets (Small / Default / Wide / Tall),
  and *Delete this spot*.
- **Multi-signer support**: every spot has an `owner` (Person
  number). Sign action signs only YOUR (current user) spots and
  leaves the others as empty signature fields for the next
  signer to fill in Acrobat / Foxit / Preview. Audit JSON lists
  only the spots that were actually signed in this pass.
- Empty signature fields in saved PDFs now carry descriptive
  names like `Signature 1 (Person 2)` so recipients see which
  spot is theirs in the signature panel.
- Deferred to v1.31: resize handles on the canvas, multiple
  saved signatures, image-upload signature method, Verify
  dialog.

## v1.29
- Sign dialog overhauled into a proper signature designer:
  - **Left-click** on an empty area of a page → places a new
    signature spot. Overlap with an existing spot is rejected with a
    status-line warning.
  - **Left-click** on an existing spot → selects it (solid blue
    outline + light blue fill).
  - **Right-click** on a spot → selects + enters *move mode* (cursor
    changes); the next left-click on a page relocates the spot.
    Right-click empty or `Esc` cancels move mode.
  - **Delete** or **Backspace** → removes the selected spot.
- New **mode toggle** at the top of the dialog:
  - **Sign this document now** (default) — sign every spot with your
    saved signature, produce signed PDF + audit JSON, as in v1.28.
  - **Prepare for others to sign** — produce a PDF with empty
    signature fields at every placed spot. No signing happens; the
    recipient fills each field in with their own signing software.
- Signed visible appearance redesigned: **signature image on the
  left half, signer name + timestamp on the right half**, with a
  thin divider. No more overlapping the signature with text.
- Default stamp size bumped from 144×48 pt to 200×60 pt to host the
  new side-by-side appearance.

## v1.28
- **NEW: 🔏 Sign and Create PDF** — fully-offline e-signature
  feature. PAdES-compliant via `pyhanko`; Adobe Acrobat / Foxit /
  Preview all show the signature panel correctly.
- New **Create Signature** dialog with two methods: **Type** (your
  name in a cursive font, with preview) and **Draw** (freehand pad,
  works with mouse or trackpad). One saved signature per user;
  multi-signature manager arrives in v1.29.
- New **Sign** dialog: scrollable preview of every page; click on
  any page to drop your stamp; click elsewhere to move it; **Sign
  & Save** finalises.
- Output: **signed PDF + `.audit.json` sidecar** with SHA256 of the
  signed file, signer identity, timestamp, and certificate
  fingerprint — for human-readable independent verification.
- **One-time self-signed certificate** generated on first sign,
  stored at `~/.config/mydocmaker/signing/`. Never
  leaves your machine. Recipients see "self-signed" until they
  trust the certificate — same trade-off as code-signing without
  a paid CA.
- New deps: `pyhanko>=0.25`, `cryptography>=42.0` (pure-Python, no
  external services). PyInstaller `--collect-all` flags added so
  the bundle works out of the box.
- v1.29 will add: image-upload signature, multiple saved
  signatures, drop multiple stamps per PDF, and a Verify dialog.

## v1.27
- Header text refreshed: *"Drop any file(s) below — or paste a website
  URL — and create a combined PDF."* — clearer about what the app
  actually produces.

## v1.26
- Nautilus right-click context-menu entry now displays the app's
  red D&D PDF icon next to "Add to D&D PDF Creator", instead of
  just the text. Resolved via the freedesktop icon name
  `mydocmaker` (already installed under
  `/usr/share/icons/hicolor/.../apps/`).

## v1.25
- **Preview tab — continuous scroll.** Replaces the page-by-page
  view from v1.23: every page is rendered stacked vertically, you
  scroll with the wheel or scrollbar, and the Prev/Next buttons
  jump to the next page boundary. Page indicator stays in sync.
- **Mouse-wheel scrolling** now works in the preview (Win/Mac via
  `<MouseWheel>`, Linux via `<Button-4>`/`<Button-5>`).
- **Window + taskbar icon quality.** Pre-resizes the source PNG to
  seven standard icon sizes (16–256) with Pillow's LANCZOS filter
  and feeds them all to `iconphoto`, so the WM picks the best size
  for each context. No more blurry taskbar icon.
- New: **"Sign and Create PDF" button** next to *Create PDF*.
  Grayed out for now — wires up to actual PAdES e-signature in
  v1.26.
- **Flatten savings estimate moved.** Was buried in the under-list
  totals strip; now sits right next to the Flatten checkbox so
  "what would I gain by ticking this" is visible at the toggle.
- **Empty-list placeholder is clickable.** Clicking "Drag & Drop
  any file here" opens the file browser — same as the
  *+ Browse files* button.
- Tiny: dropped the exclamation point from the ♡ sponsor tooltip
  to read less salesy.

## v1.24
- New: small **♡ sponsor button** in the footer, between the version
  label and *Check for updates*. Hover shows the tooltip *"Support
  this project from Dejan & Claudia!"*. Click is intentionally a
  no-op until the GitHub Sponsors profile is approved; the visual is
  in place so the next release just wires up the URL.
- Custom Tk `Tooltip` helper (lightweight, ~30 lines) — first reuse
  candidate for future hover hints on other buttons.

## v1.23
- New: **Live Preview tab**. The main window is now tabbed:
  **Pages** (the existing list editor) and **Preview** (new).
  Switching to Preview shows a live, page-by-page viewer of the
  combined PDF, with prev/next navigation and a zoom dropdown
  (Fit / 50% – 200%).
- New: **Background render pipeline**. A `RenderWorker` (2 worker
  threads) converts every newly-added file or URL to PDF bytes in
  the background as soon as it lands in the list, caching the
  bytes on the `Item`. The preview just stitches cached bytes
  together — reorder/remove is essentially instant.
- Per-item status indicators (`…` queued, `⏳` rendering, `✓` ready,
  `✗` failed) appear next to filenames in the page list so you can
  see what's still cooking.
- Changing **Page size** (Original/A4/Letter) drops cached renders
  and re-queues every item so the preview reflects the new setting.
- Cache is in-memory only (lost on app restart); re-opens re-queue
  rendering automatically. Persistent disk cache is deferred to
  a future release.
- Foundation for v1.24's e-signature: the same viewer will host
  click-to-place signature stamps.

## v1.22
- New: **Multi-backend Office conversion**. The app now tries available
  conversion backends in priority order for every `.docx` / `.xlsx` /
  `.pptx` / `.odt` / etc.:
  1. **Microsoft Office** (Windows COM via pywin32) — best fidelity for
     MS Office formats; uses the real Word / Excel / PowerPoint app
     headlessly.
  2. **OnlyOffice DocumentBuilder** — second-best MS-format fidelity;
     free, cross-platform; requires a separate ~100 MB install.
  3. **LibreOffice** — universal fallback. Existing behavior preserved.
- Windows users with Microsoft Office installed no longer need
  LibreOffice at all for Office → PDF conversion.
- If a backend fails on a specific file (e.g. Word chokes on a
  malformed .docx), the dispatcher silently retries with the next
  backend rather than failing the whole conversion.
- `pywin32>=306` added to `requirements.txt` with a `sys_platform ==
  'win32'` marker — Linux/macOS builds skip it entirely. Windows
  PyInstaller build registers `win32com.client`, `pythoncom`,
  `pywintypes` as hidden imports.

## v1.21
- New: byline on the in-app **What's New** dialog (footer version →
  click). Every version's release notes now close with
  *"by Dejan Obradovic (& Claudia)"*.

## v1.20
- New: **File sizes shown per item** in the page list — every entry
  reads `filename.ext (12.3 MB)`. URLs show `(webpage)` since their
  final size isn't known until Chromium renders them.
- New: **Running-totals strip** under the list shows item count,
  total bytes on disk, and an estimate of the output size if Flatten
  is enabled. Helps decide *before* clicking Create PDF whether
  flattening is worth turning on.
  Format: `5 items · 47.2 MB on disk · ~3.2 MB if flattened (saves
  about 93%)`.
- The flatten estimate uses each input's actual page count where
  cheap to determine (PDFs via pypdf metadata, images = 1 page each),
  and a size-based heuristic for text and Office docs.

## v1.19
- Fix: **default page size was stuck on "Original" for anyone who'd
  ever launched v1.16–v1.18**, even after v1.18 added locale-aware
  defaults. Old saved state was overwriting the locale pick. State
  files now carry a schema version; v1 saves are read for the page
  list but ignored for page-size + flatten preferences so the locale
  default applies.
- Post-install banner now mentions logging out + back in once if the
  app menu icon looks generic instead of the red D&D PDF circle —
  GNOME Shell caches icons in memory and Wayland can't live-reload.

## v1.18
- New: **Custom red D&D PDF icon** baked into every platform — Tk
  window icon, Linux app menu (256/512 hicolor), Windows taskbar +
  installer + uninstaller, macOS Dock + `.app` bundle. PyInstaller
  embeds the platform-native format (`.ico` on Windows, `.icns` on
  macOS) and the source PNG ships in the bundle for runtime
  `root.iconphoto()`.
- New: **Locale-aware default page size.** Letter for US, Canada,
  Mexico, Philippines, Colombia, Venezuela, Chile; A4 everywhere
  else. Detected from `LANG`/`LC_*` env vars or, on Windows, via
  `GetUserDefaultUILanguage`. *Original (images)* is still selectable
  but no longer the default.
- Improved: **No more LibreOffice nag if you already have any Office
  suite.** OnlyOffice (Desktop Editors or DocumentBuilder), Microsoft
  Office, or Apple iWork detected = the missing-component banner
  stays silent.
- Improved: **Install dialog now leads with OnlyOffice** as the
  recommended free Office suite (best Microsoft-format fidelity).
  LibreOffice listed as the universal alternative.
- Note: actual headless conversion via OnlyOffice / MS Office still
  needs their batch tools (OnlyOffice DocumentBuilder, MS Office
  COM). Full multi-backend support coming in v1.19.

## v1.17
- Empty Pages list now shows a friendly **"Drag & Drop any file here"**
  hint instead of being blank.
- App icon swapped to the system **`application-pdf`** icon (the look
  v1.01 had). Matches whatever your icon theme provides, instead of a
  custom blue square. .deb is also slightly smaller.

## v1.16
- New: **"Add to D&D PDF Creator" right-click entry** (Linux, Nautilus).
  A top-level menu line — no more digging through Open With submenus.
  Files are silently appended to the open window, or launch a new one
  if the app isn't running. Implemented as a python3-nautilus
  extension shipped in the .deb (`/usr/share/nautilus-python/extensions/`).
- New: **Persistent file list.** Your page list is saved to
  `~/.config/mydocmaker/state.json` after every change and
  on app close, then restored next time you launch. Page size and
  Flatten preferences are remembered too.
- Restore is smart: files that have been moved or deleted between
  sessions are filtered out, with a status-line note of the count
  ("Restored 7 item(s) from last session (2 missing file(s) were
  dropped).").
- `Clear all` button stays as the way to start fresh.
- Nautilus extension and python3-nautilus added as Recommends in the
  .deb so apt installs them alongside.

## v1.15
- Fixed: **Right-click "Open With MyDocMaker" now appears**
  in Nautilus / GNOME Files / Pop!_OS Files on Linux. The .desktop file
  was missing the `Icon=` field; without an icon, Nautilus silently
  demotes apps from the primary "Open With" submenu to "Other
  Application…" only. With this fix, the entry is in the top-level
  Open With menu for every registered MIME type.
- Linux .deb now ships a 256×256 PNG icon (generated at build time with
  Pillow), plus `GenericName=PDF Builder` and a `Keywords=` line so the
  app finds matches in menu search for "merge", "combine", etc.
- postinst now also runs `gtk-update-icon-cache` and
  `update-mime-database` so file managers pick up the new icon and
  MIME registrations immediately — no logout required.

## v1.14
- New: **One-time spreadsheet hint.** Adding a `.xlsx` / `.xls` /
  `.ods` file pops an info dialog explaining how to set Print Area +
  Fit to Page + orientation in your spreadsheet for clean PDF output.
  This addresses the most common "the output looks wrong" surprise:
  LibreOffice uses whatever print settings are saved in the file, and
  most people never touched those.
- Improved: **Windows missing-LibreOffice messaging.** Direct download
  link, three-step install instructions, and an explanation of why we
  don't bundle LibreOffice (would push the installer past 600 MB).
- New: **Per-platform Uninstall instructions** in README — Windows
  (installer + portable), macOS, Linux (.deb + portable). Plus a note
  that optional dependencies (LibreOffice, sane-utils) need to be
  removed separately.

## v1.13
- New: **Friendly install feedback for the `.deb`.** After
  `sudo apt install …` finishes, you now see a clear green ✓ banner
  with the exact command and menu name to launch the app, instead of
  just dpkg's wall of technical "Setting up… / Processing triggers…"
  output that made several test installs look like they'd failed.
- New: **Brief uninstall confirmation** with a one-line "reinstall
  with…" hint.
- Implementation: postinst + postrm scripts shipped inside the .deb;
  both refresh the desktop-file database so menu entries appear
  immediately without a logout.

## v1.12
- New: **Friendly missing-component banner.** If LibreOffice or SANE
  scanner tools aren't installed at startup, a small notice appears
  beneath the header with an *Install…* button.
- New: **One-click install dialog.** Shows each missing component with
  a brief explanation and an Install button. On Linux: detects the
  package manager (apt/dnf/pacman/zypper) and runs the install via
  `pkexec` (polkit auth prompt). On macOS: uses Homebrew if available.
  On Windows or unsupported distros: opens the official download page
  in your browser.
- New: **Dependabot configured.** Weekly PRs bump the Python deps
  baked into the bundle (Pillow, pypdf, playwright, etc) and the
  GitHub Action versions used by the workflow. Each PR re-runs the
  matrix build to catch regressions, so released installers always
  ship with current upstream libraries.

## v1.11
- Hotfix: Linux builds in v1.06–v1.10 wouldn't launch on systems with
  glibc < 2.38 (Pop!_OS 22.04, Ubuntu 22.04, Debian 12, Linux Mint 21).
  PyInstaller compiled the bundle against the newer glibc on the
  ubuntu-latest (24.04) runner, producing
  `libm.so.6: version 'GLIBC_2.38' not found` when loading the bundled
  libpython3.12.
- Pin the Linux build to `ubuntu-22.04` so the binary works on glibc
  >= 2.35 — covers every Debian/Ubuntu derivative released since April
  2022. macOS and Windows builds are unchanged.

## v1.10
- New: **One-click auto-update.** "Check for updates" now opens an
  in-app dialog with the release notes excerpt, the file size, and a
  Download & install button. A progress bar reports MB downloaded /
  total / percent.
- New: **Install-kind detection.** The app sniffs whether it's running
  from the Windows installer, a portable zip, the macOS `.app`, a Linux
  `.deb`, or a tarball — and picks the right release asset for each.
- New: **OS-native installer handoff.** Once the download finishes:
  - Windows installer build: launches the new `Setup.exe`, then closes
    the running app so Inno Setup can replace files.
  - Linux `.deb` build: `xdg-open` hands the file to GNOME Software /
    KDE Discover / `gdebi` for a one-click install.
  - macOS `.app`, Windows portable, Linux tarball: opens the download
    folder so you can drag the new build into place.
- Existing footer "Check for updates" button now goes through this
  new flow — no protocol/UI change for users, just a much shorter path
  to actually being on the latest version.

## v1.09
- Hotfix: the v1.08 build compiled the Windows installer `.exe` but
  Inno Setup's `OutputDir=.` resolves relative to the .iss script's
  folder, so the file landed in `installer/` instead of the workspace
  root and didn't get picked up for upload. The release page never got
  the installer.
- Fix: workflow now passes `/O$PWD` to ISCC and verifies the .exe exists
  before the build step succeeds — if Inno Setup ever fails again it'll
  break the build instead of silently shipping without the installer.

## v1.08
- New: **Windows installer (.exe)** — proper Inno Setup installer that
  ships alongside the portable zip. Adds right-click "Open With MyDocMaker"
  registry entries for every supported file extension, an
  optional Send To shortcut for multi-file selection in a single
  invocation, Start Menu + Desktop shortcuts, and a real uninstaller
  visible in Apps & Features. Per-user install, no admin required.
- New: **macOS Finder integration** — the bundled `.app` now declares
  `CFBundleDocumentTypes` for all supported file extensions, so right-click
  → Open With shows MyDocMaker on macOS. Multi-file selections
  arrive via Apple Events (`::tk::mac::OpenDocument`) into a single window.
- Improved: **Scan button on Windows + macOS** — instead of "coming soon",
  it now opens Windows Fax & Scan / Image Capture so users can scan,
  save, and drag the file in. Direct one-click WIA / ImageCaptureCore
  integration is still planned for a later release.
- Improved: release page lists the Windows installer separately from the
  portable zip so non-technical users see the right download first.

## v1.07
- New: **Clickable version label** in the footer — opens a "What's new in
  vX" dialog with the current release's highlights, plus a link to the
  full GitHub release history.
- New: **Close button** in the footer, alongside *Check for updates*.
  Both centered.
- Fixed: **Scan button no longer clipped.** Add-source buttons (Browse,
  From phone, Scan) moved to their own row so they always fit, even on
  narrower windows.

## v1.06
- New: **Create and open PDF** + **Create and print PDF** buttons next to
  Create PDF — build, then auto-open with the OS default viewer / send
  to the default printer.
- New: **📱 Add from phone (QR)** — pops a QR code containing a one-time
  tokenized URL pointing at a local HTTP server on this machine. Scan with
  your phone's camera, pick photos or PDFs, they appear in the page list.
  Requires phone + computer on the same Wi-Fi.
- New: **🖨 Scan** — on Linux, uses `scanimage` (SANE) to pull a 200dpi
  PNG straight from your scanner into the list. Win/Mac show a "coming
  in v1.07" notice for now.
- New: **Check for updates** button (footer) — asks the GitHub releases API
  and offers to open the downloads page if a newer tag exists.
- New: **Live flatten progress bar** + the success dialog now reports
  `Saved X.X MB (Y%)` after a flatten.
- Improved: **Save dialog defaults to your Desktop folder** instead of the
  current working directory.
- Fixed: **Webpage capture renders properly** — forces print media + light
  color scheme and clears any selected text/active element before
  snapshot, eliminating the all-gray output some sites produced in v1.05.

## v1.05
- New: **Right-click context menu** on the page list — *Remove*, *Move to
  top*, *Move to bottom*. Works on Linux/Windows (right mouse button) and
  macOS (two-finger click / Ctrl-click).
- New: [`THIRD-PARTY-LICENSES.md`](THIRD-PARTY-LICENSES.md) — explicit
  license catalogue for the bundled libraries plus a pointer to the
  Chromium/PDFium upstream license texts.
- Docs: README's example release tag now matches the current version.

## v1.04
- New: **Flatten output** checkbox — rasterizes each page to JPEG and
  re-embeds it. Often shrinks the result a lot for image-heavy PDFs.
  Selectable text and links are lost (the page becomes a picture).
  Powered by `pypdfium2`, bundled in all installers.
- New: **120 MB per-file cap** on inputs. Files over the limit are skipped
  with a single summary dialog at the end of the add batch (no per-file
  spam when you drop a folder).
- Refactor: the file browser, drag-and-drop, command-line, and right-click
  IPC handlers all funnel through the same `add_paths` entry point.

## v1.03
- New: **Right-click "Open With MyDocMaker"** on Linux. Selecting
  one or many files in your file manager and choosing the app adds them to
  the page list. Works from the `.deb` install via MIME registration.
- New: Command-line file arguments — `mydocmaker file1.png
  doc.pdf` pre-loads those files.
- New: **Single-instance mode.** If the app is already running and you
  right-click another batch of files to "Open With" it, the new files are
  appended to the existing window (the window also pops to the front)
  instead of opening a duplicate.

## v1.02
- New: Debian/Ubuntu **`.deb` package** — install with one click and get a
  desktop launcher under "Office".
- New: **Source tarball** attached to each release for easy "run from source".
- Fix: Windows download is now honestly named `MyDocMaker-Windows.zip`
  (it's a folder bundle, not a single `.exe`).
- Fix: URLs are validated before launching the headless browser — clear error
  instead of a long hang on garbage input.
- Fix: When Office files are queued but LibreOffice isn't installed, the app
  warns up front instead of silently skipping each one.
- Fix: Closed a small file-handle leak when merging existing PDF inputs.

## v1.01
- Cross-platform: now runs on Windows, macOS, and Linux from one codebase
  (rewritten UI in Tkinter).
- New: paste a website **URL** to capture a full webpage as multi-page PDF
  (A4 or Letter), powered by headless Chromium.
- Automated downloads: GitHub Actions builds Windows/macOS/Linux apps on each
  release tag — users just download and run, no coding needed.
- Carries over from the Linux version: drag & drop any time, HEIC/HEIF/AVIF
  support, many image types, folder drops, EXIF auto-rotate, reorder/remove,
  text/code/PDF/Office conversion.

## v1.00 (Linux/GTK, internal)
- Original drag-and-drop PDF creator for Pop!_OS.
