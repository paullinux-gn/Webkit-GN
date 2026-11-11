# Webkit-GN

A native GNOME word processor built with **GTK4, libadwaita, WebKitGTK 6 and
ProseMirror**. The editor runs locally; it opens and saves self-contained HTML.

## Run on CachyOS / Arch GNOME

```sh
sudo pacman -Syu --needed gtk4 libadwaita webkitgtk-6.0 python python-gobject poppler
./run.sh
```

Run inside your desktop session. The compiled JavaScript bundle is included;
Node, npm and Rust are not required to run the app. The default is a 125% A4-width
view, a light document/header and dark toolbar, with blur off. Interface settings
are saved between launches. Older settings receive the previously introduced
one-time default-theme migration.

## Features

- Two-row floating toolbar, compact themed menus and light/dark/mixed themes.
  Optional header/toolbar blur, opacity and intensity controls.
- Body, Title and H1–H3 styles, custom named styles, font search, font sizes,
  emphasis, sub/superscript, alignment and line spacing (including 0.95).
  Custom styles have delete icons in the dropdown and a Delete style button in
  their editor. Affected paragraphs return to the matching built-in style; text,
  direct formatting, alignment and spacing are retained. Ctrl+Z restores the style.
- Matching 60-colour text/highlight palettes with consistent hue columns and
  light-to-dark shades. Rounded highlights choose contrasting text automatically.
- Bulleted, numbered and interactive checklists; links and horizontal rules.
- Editable tables, header rows, border/width settings, wrapping, deletion and
  commands to continue above/below a table. Rounded, coloured text boxes.
- Embedded pictures with a proportional size dialog and direct drag handles.
  Resizing has a live size readout, Escape cancellation and one-step undo.
- One-, two- and three-column sections. A manual page break ends the column
  setting; following text is full width until another layout is selected.
- Search/replace and a live document-outline dropdown below the toolbar.
- Undo/redo, native image chooser, A4 printing and a separate PDF preview with
  page navigation, margins and orientation settings.

**File formats:** open/save HTML; PDF through the print dialog. DOCX/ODT conversion
and automatic A4 page boundaries while editing are not implemented. The editor
uses a continuous writing surface. Printing uses real paginated output, including
a print-only column layout to work around WebKit's CSS-column printing behaviour.

## Shortcuts

| Action | Shortcut |
|---|---|
| New / Open / Save | Ctrl+N / Ctrl+O / Ctrl+S |
| Save as | Ctrl+Shift+S |
| Find / Replace | Ctrl+F / Ctrl+H |
| Document outline | Ctrl+Shift+O |
| Page break | Ctrl+Enter |
| Print / Print preview | Ctrl+P / Ctrl+Shift+P |
| Leave table below / above | Alt+Enter / Alt+Shift+Enter |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |

Double-click a picture to open its size controls; click it once for drag handles.
Use a table's properties handle or the toolbar table button to edit/delete it.

## Build a Flatpak

On CachyOS / Arch:

```sh
sudo pacman -S --needed flatpak flatpak-builder
./scripts/build-flatpak.sh
```

This adds the Flathub remote for your user, downloads the GNOME 51 SDK/runtime,
builds the pinned PDF-preview utilities and creates **`dist/Webkit-GN.flatpak`**.
The first build downloads a substantial SDK; subsequent builds reuse its cache.
The host desktop does not need to run GNOME 51 for ordinary editing. Native blur requires GNOME 51+ on Wayland. No Node or Rust build is needed:
the manifest installs the checked-in production JavaScript bundle.

Install and launch:

```sh
flatpak install --user dist/Webkit-GN.flatpak
flatpak run io.github.paullinux_gn.WebkitGN
```

`./scripts/build-flatpak.sh --install` builds and installs in one step.
Alternatively, in GitHub open **Actions → Flatpak bundle → Run workflow**. Download
`Webkit-GN-flatpak-x86_64` from the completed run's Artifacts and extract the ZIP
before installing the `.flatpak` file. The workflow also runs after packaging or
application changes on `main`; it does not submit the app to Flathub.

The sandbox uses native file portals, Wayland/X11, GPU rendering and the CUPS
socket for printing. It has no blanket home-directory access or network grant.
Use `.html`/`.htm` when saving in the portal. Embedded images are preserved;
relative images in neighbouring files may be inaccessible unless separately
permitted. App settings use Flatpak's private configuration directory.

## Development and checks

Requires Node.js 22+ and Python 3 for development:

```sh
npm ci --prefix webkit
npm test --prefix webkit
python3 -m unittest discover -s webkit/tests -v
npm run build --prefix webkit
npm run benchmark --prefix webkit
```

The production build is minified; readable source and dependency notices remain
included. GitHub Actions runs unit tests and verifies the checked-in bundle is
reproducible. GTK/WebKit are needed only for native tests and the application.

Native regression tests need an X11 display, XTest, ImageMagick and Poppler:

```sh
DISPLAY=:99 ./scripts/webkit-env.sh ./scripts/test-native.sh
```

Use a disposable Xvfb display. Results and screenshots go into ignored `.runtime/`.
The cloud runtime helpers support locally unpacked Debian libraries when needed;
normal desktop installations use system packages. `scripts/setup-cloud.sh` is the
optional cloud dependency setup, not part of the desktop launch path.

The Python shell lives in `webkit/app.py`; editor modules are under `webkit/src/`.
`webkit/tests/` contains editor, file-I/O, settings and native interaction tests.
Performance measurements and cleanup notes are in [PERFORMANCE.md](PERFORMANCE.md).

## Licences and icon

See [LICENSE](LICENSE) and [dependency notices](webkit/THIRD_PARTY.md).
The app icon is GNOME's Adwaita document icon, credited to the
[GNOME Project](https://www.gnome.org). Its licence and attribution are included in
[data/ADWAITA-LICENSE.txt](data/ADWAITA-LICENSE.txt).

Flatpak packaging checks validate matching application IDs, the desktop entry and document-portal save behaviour. A full SDK/runtime build requires Flathub access; the GitHub Flatpak workflow performs that build and uploads the resulting bundle.

Blur geometry is calibrated between GTK widget coordinates and the actual WebKit viewport, including page scale and scrollbar gutters. Version 0.26.1 fixes displaced toolbar backgrounds observed in Flatpak. Native regression tests check toolbar, search and outline backdrops at 100%, 110%, 125% and 150% WebKit zoom, without changing document zoom or dirty state.

Native blur follows Twinly's GTK 4.24+/Wayland capability check. The Flatpak now uses GNOME Platform/SDK 51 so popovers, context menus, dropdowns and the hamburger menu can use GTK backdrop blur with the selected tint and radius. On older GTK or X11, the existing document/toolbar blur fallback remains available; menus remain solid. Blur off always restores solid menu backgrounds.

The application and its GTK/WebKit controls use English even on a Dutch-language desktop. Message language is selected before toolkit initialisation, without changing document contents or regional date/number preferences. External desktop portals (such as the system file picker) run outside the app and can retain the desktop's own language. Restart the app after updating to apply the interface-language change.

Choose **Page margins…** in the main menu (Ctrl+Shift+M) to set top, bottom, left and right margins in millimetres (0–90 mm; default 20 mm). Apply saves them as part of the document, with undo support. HTML exports retain these values and browser print margins. The native Print dialog starts with the document margins; its **Margins** tab adjusts them for that print job. Use **Update preview** after changing print settings. Print-only adjustments do not change the saved document.

The 125% editing view scales the page and all four margins together. Toolbar clearance sits outside the page, so it does not add to the top margin. Screen millimetres depend on monitor scaling; use print preview to check physical page placement. The editor remains a continuous document rather than a paginated view.
