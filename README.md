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
