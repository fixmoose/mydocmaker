# Third-Party Licenses

This project bundles the libraries listed below. Each is used under its own
upstream license — none are modified. Copyright remains with the respective
upstream authors. Where required, the upstream license text and notices ship
inside the relevant Python package on disk (the installer/PyInstaller bundle
copies them in alongside the library).

## Python libraries

| Library          | License             | Project page                                            |
|------------------|---------------------|---------------------------------------------------------|
| **pypdf**        | BSD-3-Clause        | https://github.com/py-pdf/pypdf                         |
| **Pillow**       | HPND (MIT/CMU-style)| https://github.com/python-pillow/Pillow                 |
| **pillow-heif**  | Apache-2.0          | https://github.com/bigcat88/pillow_heif                 |
| **reportlab**    | BSD-3-Clause        | https://www.reportlab.com/opensource/                   |
| **tkinterdnd2**  | MIT                 | https://github.com/pmgagne/tkinterdnd2                  |
| **playwright**   | Apache-2.0          | https://github.com/microsoft/playwright-python          |
| **pypdfium2**    | Apache-2.0 / BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2       |

## Bundled native components

The PyInstaller installers also embed two large native components for offline
operation. Their full license texts are large; we point at the upstream
sources rather than reproducing them inline.

- **Chromium** — embedded via `playwright` for the "paste a URL" webpage
  capture feature. Chromium is BSD-3-Clause, but the Chromium build aggregates
  many third-party components, each with its own license. The complete list
  is reproduced in the Chromium source tree at
  https://chromium.googlesource.com/chromium/src/+/main/LICENSE and the
  generated `about:credits` page inside any Chromium build.

- **PDFium** — embedded via `pypdfium2` for the "Flatten output" page
  rasterizer (introduced in v1.04). PDFium is BSD-3-Clause with subcomponents
  under Apache-2.0 and other compatible licenses. See
  https://pdfium.googlesource.com/pdfium/+/main/LICENSE for the full text.

## License compatibility note

All upstream licenses listed above are permissive (MIT / BSD / Apache /
HPND). MyDocMaker itself is released under the **PolyForm Noncommercial
License 1.0.0** (see [LICENSE](LICENSE)) — free for personal use, with
commercial use requiring a separate license. Permissive upstream licenses
allow the combined work to be redistributed under those terms, subject to the
usual requirement to preserve copyright notices and license text in
source-form distributions and in the bundled installer.

## Not bundled: office suites

LibreOffice and OnlyOffice are **not** shipped with MyDocMaker. They are
optional, user-installed programs that MyDocMaker detects and invokes as
separate processes for Office-document conversion. MyDocMaker can help you
download one (see "Install…" in the app), but the download comes from the
upstream project and the install is your own — nothing from either suite is
redistributed by us, so neither project's license attaches to this one.

For the record, if that ever changed: LibreOffice is MPL-2.0 and could be
redistributed; OnlyOffice Desktop Editors is AGPL-3.0 and could not be, not
without a commercial license from Ascensio System SIA.

## Where the license texts live in the bundle

When PyInstaller produces the Windows/macOS/Linux bundles, the upstream
license files that ship inside each Python package (e.g.
`site-packages/pypdf-*.dist-info/LICENSE`) are carried along inside the
bundle directory. End users wanting to read the verbatim text of any
particular upstream license can extract the bundle and find the relevant
`*.dist-info/LICENSE` files alongside the application.

## Not bundled: other PDF editors

Evaluated and deliberately not used, recorded so the question isn't reopened:

| Project | Licence | Why not |
| --- | --- | --- |
| [Stirling-PDF](https://github.com/Stirling-Tools/stirling-pdf) | MIT shell; `engine/`, `frontend/src/editor/proprietary/`, `frontend/src/processor/` and the `app/proprietary/`, `app/saas/` trees under the "Stirling PDF User License" | Open-core. The editor itself is the proprietary part: "Production use of the Stirling PDF Software is only permitted with a valid Stirling PDF User License." Also Java/Gradle, so reuse would mean shipping a JVM. |
| [word-sys-pdf-editor](https://github.com/word-sys/word-sys-pdf-editor) | GPL-3.0-or-later | Free of charge, but strong copyleft: incorporating its code would license all of MyDocMaker under GPL-3.0, which cannot coexist with PolyForm Noncommercial plus a paid commercial tier. It also depends on PyMuPDF (AGPL-3.0), which is why it is GPL in the first place. |
| [open-pdf-studio](https://github.com/OpenAEC-Foundation/open-pdf-studio) | LGPL-3.0 | Free and the only licence-compatible one of the three — LGPL allows linking from a differently-licensed application when the library ships as a replaceable dynamic library with source available. Not used because it is a separate Rust/Tauri desktop application whose rendering is PDFium, which this app already uses via pypdfium2. |

Checked 2026-11-02.
