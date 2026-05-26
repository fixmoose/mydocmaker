# MyDocMaker

**A cross-platform PDF maker for everyone — no coding required.**

Drop in files, paste a website link, reorder everything, click **Create PDF**.
Sign it with a tamper-proof DocuSign-style stamp if you want.
Works on **Windows, macOS, and Linux**.

🌐 [mydocmaker.com](https://mydocmaker.com)

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Version](https://img.shields.io/badge/version-1.0-green)
![License](https://img.shields.io/badge/license-PolyForm--NC--1.0-lightgrey)
![Personal use](https://img.shields.io/badge/personal%20use-free-brightgreen)

---

## ⬇️ Download (no install, no coding)

Go to the [**Releases**](../../releases/latest) page and download the file for
your computer:

| Your computer | Download | How to run |
|---------------|----------|-----------|
| **Windows (installer)** | `MyDocMaker-Windows-Setup.exe` | Run → next, next, finish. Adds right-click "Open With", SendTo, Start Menu shortcut. |
| **Windows (portable)** | `MyDocMaker-Windows.zip`     | Unzip → open the folder → double-click **MyDocMaker.exe** |
| **macOS**     | `MyDocMaker-macOS.zip`       | Unzip → **right-click the app → Open** (first time only). |
| **Linux (.deb)** | `mydocmaker_1.0_amd64.deb` | `sudo apt install ./mydocmaker_1.0_amd64.deb` |
| **Linux (portable)** | `MyDocMaker-Linux.tar.gz` | Extract → run `MyDocMaker` inside the folder |
| **Source**    | `MyDocMaker-Source.tar.gz`   | For developers — see [For developers](#-for-developers-run-from-source) below |

> **First-launch note:** Windows builds aren't code-signed yet, so
> SmartScreen will show "Windows protected your PC" → click **More
> info → Run anyway**. macOS: right-click the app → Open → Open again.
> You only do this once per machine.

## 🗑️ Uninstall

| Your computer | How to uninstall |
|---------------|------------------|
| **Windows (installer)** | Start menu → *Add or Remove Programs* → search **MyDocMaker** → **Uninstall**. |
| **Windows (portable)** | Delete the folder you unzipped. |
| **macOS** | Open **/Applications** → drag *MyDocMaker* to the Trash → empty Trash. |
| **Linux (.deb)** | `sudo apt remove mydocmaker`. |
| **Linux (portable)** | Delete the folder you extracted. |

---

## ✨ What it does

- **Drag & drop anything, any time** — drop files from your file manager,
  the desktop, or another window. New drops add to the list.
- **Paste a website link** and capture the full webpage as PDF pages —
  automatically split across multiple **A4** or **Letter** pages.
- **iPhone photos (HEIC)** work out of the box — plus HEIF and AVIF.
- **Mix and match** — combine photos, documents, PDFs, and webpages into one
  PDF, in whatever order you choose.
- **Reorder & remove** pages before building.
- **Big files welcome** — accepts inputs up to **120 MB** each.
- **Flatten output** to shrink image-heavy PDFs.
- **Create and Open** / **Create and Print** — one-click variants.
- **Add from phone (QR)** — scan a QR with your phone to upload photos/PDFs.
- **Scan from scanner** (Linux today, Windows/macOS planned) via SANE.
- **🔏 E-signature** — DocuSign-style stamps in three modes:
  - **Digital** — full business signature with name, company, address,
    VAT/EIN/Tax/License + auto-rendered cursive name visual + SHA-256
    badge + timestamp
  - **Typed** — type your name in a polished cursive script
  - **Drawn** — freehand drawing with anti-aliased smoothing
- **Tamper-proof signatures** — the signature visual is baked into the
  page's content stream (basic PDF editors can't quietly delete it),
  plus a visible Acrobat-style cryptographic widget on top, plus
  `MDPPerm.FILL_FORMS` certification so any tampering invalidates the
  signature in Acrobat.
- **Multiple saved signatures** — manage them with the **My Signatures**
  button; right-click any signature window in the sign dialog to pick
  which signature to apply.
- **▼ Archive folder** — opt-in: pick a folder once and every signed
  PDF gets auto-saved there as a flattened copy, as a backup.

## 📄 Supported inputs

| Category   | What you can drop / add |
|------------|--------------------------|
| Images     | png, jpg, jpeg, bmp, gif, tiff, webp, ico, ppm/pgm/pbm, tga, **heic, heif, avif** |
| Webpages   | any **URL** (paste the link) |
| PDFs       | pdf (merged in as-is) |
| Text/code  | txt, md, csv, log, py, js, ts, html, css, json, xml, yaml, ini, sh |
| Office docs| doc, docx, odt, rtf, xls, xlsx, ods, ppt, pptx, odp *(needs LibreOffice or MS Office installed)* |

## 🖱️ How to use

1. Open the app.
2. **Drop files** onto the big list area, **and/or** paste a **website link**
   in the box at the top and click *Add webpage*.
3. Drag-reorder using **↑ Up / ↓ Down**, or **Remove** anything you don't want.
4. Pick a **page size** (Original / A4 / Letter).
5. Click **Create PDF** and choose where to save. Done.

To sign: click **🔏 Sign and Create PDF** → place signature windows on the
preview → pick a signature via right-click → **Sign & Save**.

---

## 🛠️ For developers (run from source)

```bash
git clone https://github.com/fixmoose/mydocmaker.git
cd mydocmaker
pip install -r requirements.txt
python -m playwright install chromium     # for webpage capture
python mydocmaker.py
```

Built with Python + Tkinter (cross-platform GUI), `tkinterdnd2` (drag & drop),
`pillow-heif` (HEIC), `playwright` (webpage capture), `pypdf` + `reportlab`
(PDF assembly), `pyhanko` + `cryptography` (PAdES e-signatures).

### How the downloads are built

There's nothing to compile by hand. The
[`.github/workflows/build.yml`](.github/workflows/build.yml) GitHub Actions
workflow builds the Windows, macOS, and Linux apps automatically and attaches
them to a Release whenever a version tag (e.g. `v1.0`) is pushed.

## 📜 License

**MyDocMaker is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE)**.

- ✅ **Free for personal, charity, educational, research, and government use.**
- ❌ **Not free for commercial use.** Any use at, by, or on behalf of a
  for-profit company (including internal use) requires a separate
  commercial license.

### 💼 Commercial licensing

Contact **licensing@mydocmaker.com** to obtain a commercial license. Terms
are reasonable; pricing scales with company size.

## 🙌 Why this exists

Built so anyone can turn anything into a polished, signed PDF without
fighting bloated apps. Personal use stays free forever; commercial
licensing keeps the project alive. Peace! ~Dejan
