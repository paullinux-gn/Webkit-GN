"""HTML/image I/O for the WebKit editor, without remote resource requests."""
import base64
import html
from html.parser import HTMLParser
import os
from pathlib import Path
import tempfile
from urllib.parse import unquote, urlsplit


def image_uri(path):
    data = Path(path).read_bytes()
    if len(data) > 20*1024*1024:
        raise ValueError("Choose an image smaller than 20 MB.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("Supported images: PNG, JPEG, GIF and WebP.")
    return "data:"+mime+";base64,"+base64.b64encode(data).decode("ascii")


class EmbeddedImages(HTMLParser):
    def __init__(self, directory):
        super().__init__(convert_charrefs=False)
        self.directory = directory.resolve()
        self.parts = []
        self.omitted = 0

    def tag(self, tag, attrs, closing):
        if tag == "img":
            attrs = dict(attrs)
            attrs.pop("srcset", None)
            src = attrs.get("src", "")
            if not src.lower().startswith("data:image/"):
                url = urlsplit(src)
                try:
                    if url.scheme or url.netloc or not url.path:
                        raise ValueError("External image")
                    path = (self.directory/unquote(url.path)).resolve()
                    # Imported markup must not read arbitrary files outside its own tree.
                    if not path.is_relative_to(self.directory):
                        raise ValueError("Image outside document folder")
                    attrs["src"] = image_uri(path)
                except (OSError, ValueError):
                    self.omitted += 1
                    self.parts.append(html.escape(attrs.get("alt") or "[Image unavailable]"))
                    return
            attrs = attrs.items()
        attributes = "".join(" "+key+("=\""+html.escape(value, quote=True)+"\"" if value is not None else "") for key, value in attrs)
        self.parts.append("<"+tag+attributes+("/>" if closing else ">"))

    def handle_starttag(self, tag, attrs): self.tag(tag, attrs, False)
    def handle_startendtag(self, tag, attrs): self.tag(tag, attrs, True)
    def handle_endtag(self, tag): self.parts.append("</"+tag+">")
    def handle_data(self, data): self.parts.append(data)
    def handle_entityref(self, name): self.parts.append("&"+name+";")
    def handle_charref(self, name): self.parts.append("&#"+name+";")
    def handle_decl(self, declaration): self.parts.append("<!"+declaration+">")


def read_html(path):
    path = Path(path)
    if path.suffix.lower() not in (".html", ".htm"):
        raise ValueError("This prototype opens HTML files. ODT and DOCX conversion is not implemented yet.")
    data = path.read_bytes()
    if len(data) > 64*1024*1024:
        raise ValueError("This prototype supports HTML documents up to 64 MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Please convert this HTML file to UTF-8 before opening it.") from error
    parser = EmbeddedImages(path.parent)
    parser.feed(text)
    parser.close()
    return {"html":"".join(parser.parts), "omitted":parser.omitted}


def write_html(path, content):
    path = Path(path)
    if path.suffix.lower() not in (".html", ".htm"):
        raise ValueError("Save this document with an .html extension.")
    # A document-portal grant covers the selected file, not sibling temporary
    # files or renames. Write that exported file directly; normal paths retain
    # the existing atomic-save behaviour.
    portal_root=Path(os.environ.get("XDG_RUNTIME_DIR",f"/run/user/{os.getuid()}"))/"doc"
    if os.environ.get("FLATPAK_ID") and Path(os.path.abspath(path)).is_relative_to(Path(os.path.abspath(portal_root))):
        with path.open("w",encoding="utf-8") as file:
            file.write(content);file.flush();os.fsync(file.fileno())
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix="."+path.name+".", delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
