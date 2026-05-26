# Changelog

## v1.0 — First public release

MyDocMaker — drag-and-drop PDF maker with tamper-proof e-signatures.

### Core features
- Drop files (images, PDFs, Office docs, text/code), paste a website URL,
  reorder, click **Create PDF**.
- Supports HEIC/HEIF/AVIF (iPhone photos) out of the box.
- Office docs via LibreOffice or MS Office; webpages via Playwright headless
  Chromium (full-page capture, A4/Letter pagination).
- "Add from phone" QR uploader — scan with your phone, photos land in the list.
- Linux scanner support via SANE.
- Optional **flatten** to rasterize the output for a smaller, lock-it-in PDF.
- "Create and Open" / "Create and Print" one-click variants.

### E-signature (PAdES via pyhanko)
- Three signature modes in the creator dialog: **Digital** (DocuSign-style
  business stamp auto-rendered from your name), **Typed**, **Drawn**.
- Per-position metadata (name, company, address, VAT/EIN/Tax/License) baked
  into the visible appearance with a ✓ SHA-256 + timestamp badge.
- **Tamper-proof signing**: the visible stamp is drawn into the page's
  content stream (basic PDF editors can't quietly delete it), plus a visible
  Acrobat-style cryptographic widget on top, plus `MDPPerm.FILL_FORMS`
  certification so any tampering invalidates the seal.
- Multiple saved signatures with a **My Signatures** manager.
- Multi-signer workflow: leave empty signature fields with named/email-tagged
  Person slots for others to fill in.

### Cross-platform packaging
- Windows installer (.exe) + portable (.zip)
- macOS .app (.zip)
- Linux .deb + portable .tar.gz
- All produced by a single GitHub Actions matrix build on tag push.

### Storage & privacy
- Settings + saved signatures live in `~/.config/mydocmaker/` (XDG-compliant).
- Optional **Archive folder**: pick a folder once and every signed PDF
  gets auto-saved there as a flattened backup copy.
- Self-signed RSA-2048 signing cert generated locally on first use — never
  leaves your machine.
