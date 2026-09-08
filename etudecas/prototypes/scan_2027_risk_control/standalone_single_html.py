#!/usr/bin/env python3
"""Build one movable, offline HTML containing the complete industrial demo.

The generated document keeps the industrial landing page as its shell.  Every
view and downloadable evidence file is gzip-compressed and embedded in that
same document.  Views are opened in a full-screen ``srcdoc`` iframe, so the
artifact works from ``file://`` without a server or neighbouring files.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import html
import io
import json
import mimetypes
import posixpath
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = "etudecas.single_html_industrial_demo.v1"
PLOTLY_PATH = "views/plotly-2.32.0.min.js"
INDEX_NAMES = {"index.html", "OUVRIR_LA_DEMONSTRATION.html"}
OPAQUE_STANDALONE_SCHEMA = "etudecas.single_html_industrial_demo.v1"
INVENTORY_PATH = "__contenu_embarque__.html"
FRAGMENT_TOKEN = "__STANDALONE_FRAGMENT_JSON__"
PLOTLY_TOKEN = "<!--__STANDALONE_PLOTLY_BUNDLE__-->"
SECURITY_PROFILE = "etudecas.single_html.offline_sandbox.v1"
MAX_SINGLE_HTML_BYTES = 128 * 1024 * 1024
MAX_ENTRY_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_ENTRY_BYTES = 256 * 1024 * 1024
MAX_ENTRY_COUNT = 2048
MAX_OPAQUE_DEPTH = 1
DECOMPRESSION_CHUNK_BYTES = 1024 * 1024
HREF_RE = re.compile(
    r"(?<![\w:-])href\s*=\s*(['\"])([^'\"]*)\1",
    re.IGNORECASE,
)
SRC_RE = re.compile(
    r"(?<![\w:-])src\s*=\s*(['\"])([^'\"]*)\1",
    re.IGNORECASE,
)
URL_ATTRIBUTE_RE = re.compile(
    r"(?<![\w:-])(?P<name>href|src|srcset|poster|action|formaction|data|ping|background|srcdoc|xlink:href)"
    r"\s*=\s*(?P<quote>['\"])(?P<value>[^'\"]*)(?P=quote)",
    re.IGNORECASE,
)
URL_ATTRIBUTE_PRESENCE_RE = re.compile(
    r"(?<![\w:-])(?:href|src|srcset|poster|action|formaction|data|ping|background|srcdoc|xlink:href)\s*=",
    re.IGNORECASE,
)
START_TAG_RE = re.compile(
    r"<(?P<tag>[A-Za-z][\w:-]*)(?P<attributes>(?:[^\"'>]|\"[^\"]*\"|'[^']*')*)>",
    re.DOTALL,
)
STYLE_BLOCK_RE = re.compile(
    r"<style\b[^>]*>(?P<content>.*?)</style\s*>",
    re.IGNORECASE | re.DOTALL,
)
SCRIPT_BLOCK_RE = re.compile(
    r"<script\b[^>]*>(?P<content>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
STYLE_ATTRIBUTE_RE = re.compile(
    r"(?<![\w:-])style\s*=\s*(['\"])(.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
CSS_URL_RE = re.compile(r"url\s*\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\b", re.IGNORECASE)
META_REFRESH_RE = re.compile(
    r"<meta\b(?=[^>]*\bhttp-equiv\s*=\s*(['\"])refresh\1)[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
NETWORK_SCRIPT_RE = re.compile(
    r"\b(?:fetch\s*\(|XMLHttpRequest\b|WebSocket\s*\(|EventSource\s*\(|"
    r"navigator\s*\.\s*sendBeacon\s*\(|importScripts\s*\(|import\s*\()",
    re.IGNORECASE,
)
HEAD_OPEN_RE = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
PLOTLY_TAG_RE = re.compile(
    r"<script\s+src\s*=\s*(['\"])plotly-2\.32\.0\.min\.js\1\s*>\s*</script>",
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
SHA256_RE = re.compile(r"[0-9a-f]{64}")
RESERVED_SOURCE_MARKERS = {
    INVENTORY_PATH,
    FRAGMENT_TOKEN,
    PLOTLY_TOKEN,
    "__EMBEDDED_FILES_JSON__",
    "__PLOTLY_BUNDLE_JSON__",
    "__STANDALONE_METADATA_JSON__",
    "const files = ",
    "const plotlyBundle = ",
    "const metadata = ",
    "window.ETUDECAS_SINGLE_HTML",
    "singleHtmlRuntime",
    "singleHtmlShellStyle",
    "singleFileNotice",
    "standaloneViewer",
    "standaloneFrame",
}
SINGLE_CSP_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline' blob:; "
    "style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; "
    "font-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-src about: data: blob:; "
    "child-src about: data: blob:; worker-src blob:"
)
PORTABLE_CSP_POLICY = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' blob:; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "media-src 'self' data: blob:; font-src 'self' data:; connect-src 'none'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'; "
    "frame-src about: data: blob:; child-src about: data: blob:; "
    "worker-src blob:"
)
CSP_META_ID = "etudecasOfflineCsp"
CSP_META_RE = re.compile(
    rf"<meta\b(?=[^>]*\bid\s*=\s*(['\"]){CSP_META_ID}\1)[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
ENTRY_REQUIRED_FIELDS = {
    "kind",
    "title",
    "mime",
    "source_bytes",
    "source_sha256",
    "embedded_bytes",
    "embedded_sha256",
    "needs_plotly",
    "gzip_base64",
}
ENTRY_OPTIONAL_FIELDS = {"opaque_standalone"}
PLOTLY_FIELDS = {
    "source_bytes",
    "source_sha256",
    "embedded_sha256",
    "gzip_base64",
}
METADATA_REQUIRED_FIELDS = {
    "schema_version",
    "generated_at_utc",
    "source_package",
    "view_count",
    "embedded_entry_count",
    "requires_internet",
    "requires_local_server",
    "plotly_source_sha256",
}
METADATA_OPTIONAL_FIELDS = {
    "plotly_embedded",
    "opaque_standalone_view_count",
    "index_aliases",
    "security_profile",
    "max_entry_bytes",
    "max_total_entry_bytes",
    "opaque_max_depth",
    "memory_budget_note",
}
WINDOWS_INVALID_NAME_CHARS = set('<>:"|?*')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


CHILD_BRIDGE = r"""
<script>
(() => {
  const requestedFragment = __STANDALONE_FRAGMENT_JSON__;
  const send = (type, path, fragment) => parent.postMessage({
    source: "etudecas-single-html",
    type,
    path: path || "",
    fragment: fragment || ""
  }, "*");
  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-standalone-view],[data-standalone-download],[data-standalone-close]") : null;
    if (!target) return;
    event.preventDefault();
    if (target.dataset.standaloneClose !== undefined) {
      send("close");
    } else if (target.dataset.standaloneView) {
      send("view", target.dataset.standaloneView, target.dataset.standaloneFragment || "");
    } else if (target.dataset.standaloneDownload) {
      send("download", target.dataset.standaloneDownload);
    }
  });
  const openRequestedPanel = () => {
    if (requestedFragment !== "#resilience-scan") return;
    let attempts = 0;
    const timer = setInterval(() => {
      const button = document.getElementById("scanDashboardBtn");
      if (button && !button.classList.contains("hidden")) {
        button.click();
        clearInterval(timer);
      } else if (++attempts > 600) {
        clearInterval(timer);
      }
    }, 50);
  };
  if (document.readyState === "complete") setTimeout(openRequestedPanel, 0);
  else window.addEventListener("load", openRequestedPanel, {once: true});
})();
</script>
"""


SHELL_STYLE = r"""
<style id="singleHtmlShellStyle">
  #singleFileNotice{max-width:1240px;margin:14px auto 0;padding:13px 18px;border:1px solid #93c5fd;border-radius:14px;background:#eff6ff;color:#153454;display:flex;gap:14px;align-items:center;justify-content:space-between;font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}
  #singleFileNotice strong{color:#0b3b70}#singleFileNotice button{border:0;border-radius:999px;padding:9px 14px;background:#123e70;color:#fff;font-weight:750;cursor:pointer;white-space:nowrap}
  #standaloneViewer[hidden]{display:none}#standaloneViewer{position:fixed;inset:0;z-index:2147483000;background:#e8eef5;display:flex;flex-direction:column}
  #standaloneViewerHeader{min-height:58px;padding:8px 14px;background:#0b2948;color:#fff;display:flex;align-items:center;gap:13px;box-shadow:0 2px 12px rgba(15,23,42,.3)}
  #standaloneViewerHeader button{border:1px solid rgba(255,255,255,.4);border-radius:999px;background:#fff;color:#123e70;padding:9px 14px;font-weight:800;cursor:pointer}
  #standaloneViewerTitle{font:750 15px/1.3 Inter,Segoe UI,Arial,sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  #standaloneViewerStatus{margin-left:auto;color:#bfdbfe;font:12px/1.3 Inter,Segoe UI,Arial,sans-serif;white-space:nowrap}
  #standaloneFrame{width:100%;height:calc(100vh - 58px);border:0;background:#fff;display:block}
  #standaloneLoading{position:absolute;inset:58px 0 0;display:grid;place-items:center;background:#e8eef5;color:#123e70;font:750 16px Inter,Segoe UI,Arial,sans-serif}
  #standaloneLoading[hidden]{display:none}body.single-view-open{overflow:hidden}
  @media(max-width:700px){#singleFileNotice{margin:10px 10px 0;align-items:flex-start;flex-direction:column}#standaloneViewerStatus{display:none}#standaloneViewerHeader{min-height:54px}#standaloneFrame{height:calc(100vh - 54px)}}
</style>
"""


SHELL_HTML = r"""
<div id="singleFileNotice">
  <div><strong>Fichier HTML unique autonome.</strong> Toutes les cartes, analyses, données légères et annexes sont incorporées ici. Aucun ZIP, serveur ou accès Internet n'est nécessaire.</div>
  <button type="button" data-standalone-view="__contenu_embarque__.html">Voir le contenu embarqué</button>
</div>
<div id="standaloneViewer" hidden aria-hidden="true">
  <div id="standaloneViewerHeader">
    <button id="standaloneCloseBtn" type="button">← Retour à la synthèse</button>
    <div id="standaloneViewerTitle">Vue embarquée</div>
    <div id="standaloneViewerStatus">Hors ligne · fichier unique</div>
  </div>
  <div id="standaloneLoading" hidden>Chargement de la vue embarquée…</div>
  <iframe id="standaloneFrame" title="Vue embarquée" sandbox="allow-scripts allow-downloads"></iframe>
</div>
"""


RUNTIME = r"""
<script id="singleHtmlRuntime">
(() => {
  "use strict";
  const files = __EMBEDDED_FILES_JSON__;
  const plotlyBundle = __PLOTLY_BUNDLE_JSON__;
  const metadata = __STANDALONE_METADATA_JSON__;
  const viewer = document.getElementById("standaloneViewer");
  const frame = document.getElementById("standaloneFrame");
  const title = document.getElementById("standaloneViewerTitle");
  const loading = document.getElementById("standaloneLoading");
  const closeButton = document.getElementById("standaloneCloseBtn");
  const maxEntryBytes = Number(metadata.max_entry_bytes || 67108864);
  let plotlyCodePromise = null;
  let frameObjectUrl = null;

  const bytesFromBase64 = (value) => {
    const raw = atob(value);
    const bytes = new Uint8Array(raw.length);
    for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
    return bytes;
  };

  const gunzip = async (encoded, declaredBytes) => {
    if (!("DecompressionStream" in window)) {
      throw new Error("Ce navigateur est trop ancien pour ouvrir le fichier autonome. Utilisez une version récente de Edge, Chrome ou Firefox.");
    }
    if (!Number.isSafeInteger(declaredBytes) || declaredBytes < 0 || declaredBytes > maxEntryBytes) {
      throw new Error("Taille déclarée invalide pour une ressource embarquée.");
    }
    if (typeof encoded !== "string" || encoded.length > Math.ceil(maxEntryBytes / 3) * 4 + 4) {
      throw new Error("Charge compressée invalide ou excessive.");
    }
    const stream = new Blob([bytesFromBase64(encoded)]).stream().pipeThrough(new DecompressionStream("gzip"));
    const reader = stream.getReader();
    const chunks = [];
    let total = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > declaredBytes || total > maxEntryBytes) {
        await reader.cancel();
        throw new Error("Une ressource embarquée dépasse sa taille déclarée.");
      }
      chunks.push(value);
    }
    if (total !== declaredBytes) throw new Error("Taille décompressée incohérente.");
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return bytes;
  };

  const digestHex = async (bytes) => {
    if (!window.crypto || !window.crypto.subtle) return null;
    const digest = new Uint8Array(await window.crypto.subtle.digest("SHA-256", bytes));
    return Array.from(digest, (value) => value.toString(16).padStart(2, "0")).join("");
  };

  const verifiedBytes = async (entry) => {
    const bytes = await gunzip(entry.gzip_base64, entry.embedded_bytes ?? entry.source_bytes);
    const expected = entry.embedded_sha256 || entry.source_sha256 || "";
    const actual = await digestHex(bytes);
    if (actual && expected && actual !== expected) throw new Error("Échec du contrôle d'intégrité d'une ressource embarquée.");
    return bytes;
  };

  const gunzipText = async (entry) => new TextDecoder("utf-8").decode(await verifiedBytes(entry));

  const plotlyCode = async () => {
    if (!plotlyCodePromise) plotlyCodePromise = gunzipText(plotlyBundle);
    return plotlyCodePromise;
  };

  const setFrameDocument = (documentText) => {
    if (frameObjectUrl) URL.revokeObjectURL(frameObjectUrl);
    frameObjectUrl = URL.createObjectURL(new Blob(
      [documentText],
      {type: "text/html;charset=utf-8"}
    ));
    frame.removeAttribute("srcdoc");
    frame.src = frameObjectUrl;
  };

  const showViewer = (label) => {
    title.textContent = label || "Vue embarquée";
    viewer.hidden = false;
    viewer.setAttribute("aria-hidden", "false");
    loading.hidden = false;
    document.body.classList.add("single-view-open");
  };

  const errorDocument = (message) => `<!doctype html><html lang="fr"><meta charset="utf-8"><style>body{font:16px/1.6 Segoe UI,Arial,sans-serif;padding:32px;color:#7f1d1d;background:#fff7ed}pre{white-space:pre-wrap}</style><h1>Impossible d'ouvrir cette vue</h1><pre>${String(message).replace(/[&<>]/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}</pre></html>`;

  const openView = async (path, fragment = "") => {
    const entry = files[path];
    if (!entry || entry.kind !== "html") throw new Error(`Vue embarquée inconnue : ${path}`);
    showViewer(entry.title || path);
    try {
      const jobs = [gunzipText(entry)];
      if (entry.needs_plotly) jobs.push(plotlyCode());
      const values = await Promise.all(jobs);
      let childDocument = values[0];
      if (!entry.opaque_standalone) {
        childDocument = childDocument.replace(
          "__STANDALONE_FRAGMENT_JSON__",
          JSON.stringify(fragment || "")
        );
      }
      if (entry.needs_plotly) childDocument = childDocument.replace(
        "<!--__STANDALONE_PLOTLY_BUNDLE__-->",
        () => "<script>" + values[1] + "<\/script>"
      );
      frame.onload = () => { loading.hidden = true; };
      setFrameDocument(childDocument);
    } catch (error) {
      loading.hidden = true;
      setFrameDocument(errorDocument(error && error.stack ? error.stack : error));
      throw error;
    }
  };

  const downloadFile = async (path) => {
    const entry = files[path];
    if (!entry) throw new Error(`Fichier embarqué inconnu : ${path}`);
    const bytes = await verifiedBytes(entry);
    const url = URL.createObjectURL(new Blob([bytes], {type: entry.mime || "application/octet-stream"}));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = entry.download_name || path.split("/").pop() || "resultat";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 15000);
  };

  const closeViewer = () => {
    viewer.hidden = true;
    viewer.setAttribute("aria-hidden", "true");
    loading.hidden = true;
    frame.onload = null;
    setFrameDocument("<!doctype html><html><body></body></html>");
    document.body.classList.remove("single-view-open");
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-standalone-view],[data-standalone-download],[data-standalone-close]") : null;
    if (!target) return;
    event.preventDefault();
    if (target.dataset.standaloneClose !== undefined) closeViewer();
    else if (target.dataset.standaloneView) openView(target.dataset.standaloneView, target.dataset.standaloneFragment || "").catch(console.error);
    else if (target.dataset.standaloneDownload) downloadFile(target.dataset.standaloneDownload).catch(console.error);
  });

  window.addEventListener("message", (event) => {
    if (event.source !== frame.contentWindow || !event.data || event.data.source !== "etudecas-single-html") return;
    if (event.data.type === "close") closeViewer();
    else if (event.data.type === "view") openView(event.data.path, event.data.fragment || "").catch(console.error);
    else if (event.data.type === "download") downloadFile(event.data.path).catch(console.error);
  });

  closeButton.addEventListener("click", closeViewer);
  window.addEventListener("keydown", (event) => { if (event.key === "Escape" && !viewer.hidden) closeViewer(); });
  window.ETUDECAS_SINGLE_HTML = Object.freeze({metadata, openView, downloadFile, closeViewer});
})();
</script>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument(
        "--index-alias",
        action="append",
        default=[],
        help="Additional root launcher name to treat as an alias of index.html.",
    )
    return parser.parse_args()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gzip_base64(data: bytes) -> str:
    return base64.b64encode(gzip.compress(data, compresslevel=9, mtime=0)).decode("ascii")


def mime_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    overrides = {
        ".csv": "text/csv;charset=utf-8",
        ".html": "text/html;charset=utf-8",
        ".json": "application/json;charset=utf-8",
        ".md": "text/markdown;charset=utf-8",
        ".txt": "text/plain;charset=utf-8",
    }
    return overrides.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def path_from_root(root: Path, relative: str) -> Path:
    return root.joinpath(*PurePosixPath(relative).parts)


def _csp_meta(policy: str) -> str:
    return (
        f'<meta id="{CSP_META_ID}" http-equiv="Content-Security-Policy" '
        f'content="{html.escape(policy, quote=True)}">'
    )


def _inject_csp(document: str, policy: str) -> str:
    hardened = _csp_meta(policy)
    if CSP_META_RE.search(document):
        return CSP_META_RE.sub(hardened, document, count=1)
    match = HEAD_OPEN_RE.search(document)
    if match is None:
        raise ValueError("HTML document has no head element for its offline CSP")
    return document[: match.end()] + hardened + document[match.end() :]


def _assert_csp(document: str, policy: str, *, label: str) -> None:
    matches = CSP_META_RE.findall(document)
    if len(matches) != 1 or _csp_meta(policy) not in document:
        raise ValueError(f"Offline CSP is missing or altered: {label}")


def _assert_no_reserved_source_markers(document: str, *, label: str) -> None:
    collisions = sorted(marker for marker in RESERVED_SOURCE_MARKERS if marker in document)
    if collisions:
        raise ValueError(
            f"Reserved standalone marker found in source HTML {label}: {collisions[0]}"
        )


def _validate_css(css: str, *, label: str) -> None:
    if CSS_IMPORT_RE.search(css):
        raise ValueError(f"CSS @import is not supported offline: {label}")
    for match in CSS_URL_RE.finditer(css):
        reference = html.unescape(match.group(2).strip())
        if not reference.startswith("#"):
            raise ValueError(f"CSS url() is not embedded offline: {label} -> {reference}")


def _validate_document_contract(
    document: str,
    *,
    label: str,
    allow_local: bool,
) -> None:
    if META_REFRESH_RE.search(document):
        raise ValueError(f"Meta refresh is not supported offline: {label}")
    for script in SCRIPT_BLOCK_RE.finditer(document):
        if NETWORK_SCRIPT_RE.search(script.group("content")):
            raise ValueError(f"Dynamic network API is not supported offline: {label}")
    for style in STYLE_BLOCK_RE.finditer(document):
        _validate_css(style.group("content"), label=label)
    for tag_match in START_TAG_RE.finditer(document):
        tag_document = tag_match.group(0)
        tag = tag_match.group("tag").casefold()
        if tag == "base":
            raise ValueError(f"HTML base element is not supported offline: {label}")
        quoted_attributes = list(URL_ATTRIBUTE_RE.finditer(tag_document))
        if len(URL_ATTRIBUTE_PRESENCE_RE.findall(tag_document)) != len(
            quoted_attributes
        ):
            raise ValueError(f"Unquoted or unsupported URL attribute: {label}")
        for style in STYLE_ATTRIBUTE_RE.finditer(tag_document):
            _validate_css(style.group(2), label=label)
        for attribute in quoted_attributes:
            name = attribute.group("name").casefold()
            reference = html.unescape(attribute.group("value").strip())
            if name not in {"href", "src", "xlink:href"}:
                raise ValueError(
                    f"Unsupported URL-bearing attribute {name}: {label}"
                )
            if not reference:
                continue
            parsed = urlsplit(reference)
            if name == "src":
                if parsed.scheme in {"data", "blob"}:
                    continue
                if parsed.scheme or parsed.netloc:
                    raise ValueError(
                        f"External source is not supported offline: {label} -> {reference}"
                    )
                if not allow_local and not reference.startswith("#"):
                    raise ValueError(
                        f"Single HTML retains a local source: {label} -> {reference}"
                    )
                continue
            if parsed.scheme or parsed.netloc:
                raise ValueError(
                    f"External reference is forbidden or executable offline: "
                    f"{label} -> {reference}"
                )
            if reference.startswith("#"):
                continue
            if name == "xlink:href" or tag != "a":
                raise ValueError(
                    f"Only anchor navigation can use a local href: {label} -> {reference}"
                )
            if not allow_local:
                raise ValueError(
                    f"Single HTML retains a local link: {label} -> {reference}"
                )


def resolve_reference(page_path: str, reference: str) -> tuple[str, str]:
    parsed = urlsplit(html.unescape(reference.strip()))
    if parsed.scheme or parsed.netloc:
        raise ValueError(f"External reference is not allowed in the single HTML: {reference}")
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(page_path), unquote(parsed.path)))
    if joined == ".." or joined.startswith("../") or joined.startswith("/"):
        raise ValueError(f"Reference escapes the package: {page_path} -> {reference}")
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return joined, fragment


def rewrite_local_links(
    document: str,
    page_path: str,
    known_paths: set[str],
    *,
    index_names: set[str] | None = None,
) -> str:
    resolved_index_names = INDEX_NAMES if index_names is None else index_names

    _validate_document_contract(document, label=page_path, allow_local=True)

    def replace_tag(tag_match: re.Match[str]) -> str:
        tag_document = tag_match.group(0)
        if tag_match.group("tag").casefold() != "a":
            return tag_document

        def replace_href(match: re.Match[str]) -> str:
            reference = match.group(2).strip()
            if not reference or reference.startswith("#"):
                return match.group(0)
            target, fragment = resolve_reference(page_path, reference)
            if target in resolved_index_names:
                return (
                    'href="#" data-standalone-close="1"'
                    f' data-standalone-fragment="{html.escape(fragment, quote=True)}"'
                )
            if target not in known_paths:
                raise FileNotFoundError(
                    f"Missing embedded link target: {page_path} -> {target}"
                )
            if target.endswith(".html"):
                return (
                    'href="#"'
                    f' data-standalone-view="{html.escape(target, quote=True)}"'
                    f' data-standalone-fragment="{html.escape(fragment, quote=True)}"'
                )
            return (
                'href="#"'
                f' data-standalone-download="{html.escape(target, quote=True)}"'
            )

        return HREF_RE.sub(replace_href, tag_document)

    return START_TAG_RE.sub(replace_tag, document)


def inline_local_sources(
    document: str,
    page_path: str,
    root: Path,
    known_paths: set[str],
) -> str:
    _validate_document_contract(document, label=page_path, allow_local=True)

    def replace_tag(tag_match: re.Match[str]) -> str:
        tag_document = tag_match.group(0)

        def replace_src(match: re.Match[str]) -> str:
            quote, reference = match.group(1), match.group(2).strip()
            if not reference or reference.startswith(("data:", "blob:")):
                return match.group(0)
            target, _fragment = resolve_reference(page_path, reference)
            if target not in known_paths:
                raise FileNotFoundError(
                    f"Missing embedded source target: {page_path} -> {target}"
                )
            source = path_from_root(root, target)
            mime = mime_type(target).split(";", 1)[0]
            if not mime.startswith(("image/", "audio/", "video/")):
                raise ValueError(f"Unsupported local src in {page_path}: {target}")
            encoded = base64.b64encode(source.read_bytes()).decode("ascii")
            return f"src={quote}data:{mime};base64,{encoded}{quote}"

        return SRC_RE.sub(replace_src, tag_document)

    return START_TAG_RE.sub(replace_tag, document)


def extract_title(document: str, fallback: str) -> str:
    match = TITLE_RE.search(document)
    return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else fallback


def _script_json(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        serialized.replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
    )


def _runtime_json_assignment(document: str, marker: str) -> object:
    if document.count(marker) != 1:
        raise ValueError(f"Runtime assignment count is invalid: {marker.strip()}")
    start = document.find(marker)
    if start < 0:
        raise ValueError(f"Runtime assignment not found: {marker.strip()}")
    source = document[start + len(marker) :].lstrip()
    try:
        value, end = json.JSONDecoder().raw_decode(source)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid runtime JSON after {marker.strip()}") from error
    serialized = source[:end]
    if serialized != _script_json(value):
        raise ValueError(f"Runtime JSON is unsafe or non-canonical: {marker.strip()}")
    return value


def _is_opaque_standalone(document: str) -> bool:
    if "window.ETUDECAS_SINGLE_HTML" not in document:
        return False
    try:
        metadata = _runtime_json_assignment(document, "const metadata = ")
    except ValueError:
        return False
    return bool(
        isinstance(metadata, dict)
        and metadata.get("schema_version") == OPAQUE_STANDALONE_SCHEMA
        and "const files = " in document
    )


def _validate_opaque_standalone_references(document: str, page_path: str) -> None:
    _validate_document_contract(document, label=page_path, allow_local=False)


def transform_view(
    document: str,
    page_path: str,
    root: Path,
    known_paths: set[str],
    *,
    index_names: set[str] | None = None,
) -> tuple[str, bool, bool]:
    if _is_opaque_standalone(document):
        _validate_single_html_document(
            document,
            label=page_path,
            opaque_depth=1,
        )
        return document, False, True
    _assert_no_reserved_source_markers(document, label=page_path)
    _validate_document_contract(document, label=page_path, allow_local=True)
    needs_plotly = bool(PLOTLY_TAG_RE.search(document))
    if needs_plotly:
        document, count = PLOTLY_TAG_RE.subn(
            PLOTLY_TOKEN,
            document,
            count=1,
        )
        if count != 1:
            raise ValueError(f"Could not replace Plotly in {page_path}")
        protocol_guard = "location.protocol==='file:'"
        if protocol_guard not in document:
            raise ValueError(f"Offline topography guard not found in {page_path}")
        document = document.replace(protocol_guard, "true", 1)
    document = inline_local_sources(document, page_path, root, known_paths)
    document = rewrite_local_links(
        document,
        page_path,
        known_paths,
        index_names=index_names,
    )
    if "</body>" not in document:
        raise ValueError(f"HTML page has no closing body tag: {page_path}")
    document = document.replace("</body>", CHILD_BRIDGE + "</body>", 1)
    document = _inject_csp(document, SINGLE_CSP_POLICY)
    _validate_document_contract(document, label=page_path, allow_local=False)
    return document, needs_plotly, False


def inventory_document(
    entries: dict[str, dict[str, object]],
    source_name: str,
    *,
    hardened: bool = True,
) -> str:
    rows: list[str] = []
    for path, entry in sorted(entries.items()):
        if path == INVENTORY_PATH:
            continue
        size = int(entry["source_bytes"])
        label = "Ouvrir" if entry["kind"] == "html" else "Télécharger"
        action = (
            f'data-standalone-view="{html.escape(path, quote=True)}"'
            if entry["kind"] == "html"
            else f'data-standalone-download="{html.escape(path, quote=True)}"'
        )
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(path)}</code></td>"
            f"<td>{size:,} octets</td>"
            f"<td><code>{html.escape(str(entry['source_sha256']))[:16]}…</code></td>"
            f'<td><button type="button" {action}>{label}</button></td>'
            "</tr>"
        )
    document = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contenu embarqué — démonstration autonome</title><style>
body{{margin:0;background:#eef3f8;color:#102a45;font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}}main{{max-width:1250px;margin:auto;padding:28px}}.hero,.panel{{background:#fff;border:1px solid #d8e2ec;border-radius:18px;padding:22px;margin-bottom:16px}}.hero{{background:linear-gradient(135deg,#081f3b,#0f766e);color:#fff}}h1{{margin:0 0 8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #d8e2ec;text-align:left;vertical-align:top}}th{{background:#f8fafc;position:sticky;top:0}}.wrap{{overflow:auto}}button{{border:0;border-radius:999px;background:#123e70;color:#fff;padding:7px 11px;font-weight:700;cursor:pointer}}code{{font-size:12px}}@media(max-width:700px){{th:nth-child(3),td:nth-child(3){{display:none}}}}
</style></head><body><main><section class="hero"><h1>Contenu embarqué</h1><p>Source : {html.escape(source_name)}. Ces fichiers sont physiquement incorporés au présent HTML unique.</p><button type="button" data-standalone-close="1">Retour à la synthèse</button></section><section class="panel"><div class="wrap"><table><thead><tr><th>Fichier</th><th>Taille source</th><th>SHA-256 source</th><th>Action</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section></main>{CHILD_BRIDGE}</body></html>"""
    return _inject_csp(document, SINGLE_CSP_POLICY) if hardened else document


def _entry(
    path: str,
    source_data: bytes,
    embedded_data: bytes,
    *,
    kind: str,
    title: str | None = None,
    needs_plotly: bool = False,
    opaque_standalone: bool = False,
) -> dict[str, object]:
    return {
        "kind": kind,
        "title": title or PurePosixPath(path).name,
        "mime": mime_type(path),
        "source_bytes": len(source_data),
        "source_sha256": sha256_bytes(source_data),
        "embedded_bytes": len(embedded_data),
        "embedded_sha256": sha256_bytes(embedded_data),
        "needs_plotly": needs_plotly,
        "opaque_standalone": opaque_standalone,
        "gzip_base64": gzip_base64(embedded_data),
    }


def _decoded_entry(entry: object, *, label: str) -> bytes:
    if not isinstance(entry, dict):
        raise ValueError(f"Invalid embedded entry: {label}")
    declared = entry.get("embedded_bytes", entry.get("source_bytes", -1))
    if (
        not isinstance(declared, int)
        or isinstance(declared, bool)
        or declared < 0
        or declared > MAX_ENTRY_BYTES
    ):
        raise ValueError(f"Invalid or excessive embedded byte count: {label}")
    try:
        encoded = entry["gzip_base64"]
        if not isinstance(encoded, str):
            raise ValueError("gzip_base64 is not a string")
        if len(encoded) > ((MAX_ENTRY_COMPRESSED_BYTES + 2) // 3) * 4:
            raise ValueError("compressed payload declaration exceeds limit")
        payload = base64.b64decode(encoded, validate=True)
        if len(payload) > MAX_ENTRY_COMPRESSED_BYTES:
            raise ValueError("compressed payload exceeds limit")
        chunks: list[bytes] = []
        total = 0
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            while True:
                chunk = stream.read(DECOMPRESSION_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > declared or total > MAX_ENTRY_BYTES:
                    raise ValueError("decompressed payload exceeds declaration")
                chunks.append(chunk)
        decoded = b"".join(chunks)
    except (EOFError, KeyError, OSError, ValueError) as error:
        raise ValueError(f"Invalid compressed payload: {label}") from error
    if len(decoded) != declared:
        raise ValueError(f"Embedded byte count mismatch: {label}")
    if sha256_bytes(decoded) != str(entry.get("embedded_sha256") or ""):
        raise ValueError(f"Embedded SHA-256 mismatch: {label}")
    return decoded


def _strict_non_negative_int(value: object, *, label: str, limit: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > limit
    ):
        raise ValueError(f"Invalid bounded integer: {label}")
    return value


def _portable_entry_key(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"Unsafe embedded entry path: {value}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value:
        raise ValueError(f"Unsafe embedded entry path: {value}")
    for part in pure.parts:
        if (
            part in {"", ".", ".."}
            or part.endswith((".", " "))
            or any(ord(character) < 32 for character in part)
            or any(character in WINDOWS_INVALID_NAME_CHARS for character in part)
            or part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
        ):
            raise ValueError(f"Unsafe embedded entry path: {value}")
    return unicodedata.normalize("NFC", value).casefold()


def _validate_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid SHA-256 field: {label}")
    return value


def _validate_single_html_document(
    document: str,
    *,
    label: str,
    opaque_depth: int,
) -> dict[str, object]:
    if opaque_depth > MAX_OPAQUE_DEPTH:
        raise ValueError(f"Opaque standalone nesting is too deep: {label}")
    if len(document.encode("utf-8")) > MAX_SINGLE_HTML_BYTES:
        raise ValueError(f"Single HTML exceeds its size budget: {label}")
    entries = _runtime_json_assignment(document, "const files = ")
    plotly_entry = _runtime_json_assignment(document, "const plotlyBundle = ")
    metadata = _runtime_json_assignment(document, "const metadata = ")
    if (
        not isinstance(entries, dict)
        or not isinstance(metadata, dict)
        or not isinstance(plotly_entry, dict)
    ):
        raise ValueError("Single HTML runtime dictionaries are invalid")
    metadata_fields = set(metadata)
    if (
        not METADATA_REQUIRED_FIELDS <= metadata_fields
        or metadata_fields - METADATA_REQUIRED_FIELDS - METADATA_OPTIONAL_FIELDS
    ):
        raise ValueError("Single HTML metadata fields are invalid")
    if (
        metadata.get("schema_version") != SCHEMA_VERSION
        or metadata.get("requires_internet") is not False
        or metadata.get("requires_local_server") is not False
        or not isinstance(metadata.get("source_package"), str)
        or not isinstance(metadata.get("generated_at_utc"), str)
    ):
        raise ValueError("Unexpected single HTML schema")
    if len(entries) > MAX_ENTRY_COUNT:
        raise ValueError("Embedded entry count exceeds its limit")
    declared_entry_count = _strict_non_negative_int(
        metadata.get("embedded_entry_count"),
        label="embedded_entry_count",
        limit=MAX_ENTRY_COUNT,
    )
    if declared_entry_count != len(entries):
        raise ValueError("Embedded entry count mismatch")
    hardened = metadata.get("security_profile") is not None
    if hardened:
        if (
            metadata.get("security_profile") != SECURITY_PROFILE
            or metadata.get("max_entry_bytes") != MAX_ENTRY_BYTES
            or metadata.get("max_total_entry_bytes") != MAX_TOTAL_ENTRY_BYTES
            or metadata.get("opaque_max_depth") != MAX_OPAQUE_DEPTH
            or isinstance(metadata.get("opaque_max_depth"), bool)
            or not isinstance(metadata.get("memory_budget_note"), str)
        ):
            raise ValueError("Hardened single HTML security metadata is invalid")
        _assert_csp(document, SINGLE_CSP_POLICY, label=label)
        frame_matches = [
            match.group(0)
            for match in START_TAG_RE.finditer(document)
            if match.group("tag").casefold() == "iframe"
            and 'id="standaloneFrame"' in match.group(0)
        ]
        if (
            len(frame_matches) != 1
            or 'sandbox="allow-scripts allow-downloads"' not in frame_matches[0]
            or "allow-same-origin" in frame_matches[0].casefold()
        ):
            raise ValueError("Standalone iframe sandbox is missing or unsafe")
    _validate_document_contract(document, label=label, allow_local=False)

    aliases = metadata.get("index_aliases", [])
    if not isinstance(aliases, list):
        raise ValueError("Index alias metadata is invalid")
    normalized_aliases: set[str] = set()
    for alias in aliases:
        if (
            not isinstance(alias, str)
            or PurePosixPath(alias).name != alias
            or not alias.lower().endswith(".html")
            or alias in {"index.html", INVENTORY_PATH}
        ):
            raise ValueError("Index alias metadata is invalid")
        normalized_alias = _portable_entry_key(alias)
        if normalized_alias in normalized_aliases:
            raise ValueError("Index alias metadata contains a collision")
        normalized_aliases.add(normalized_alias)
    forbidden_entry_names = {"index.html", *INDEX_NAMES, *aliases}
    normalized_keys: set[str] = set()
    download_names: set[str] = set()
    opaque_count = 0
    html_count = 0
    total_declared_bytes = 0
    decoded_entries: dict[str, bytes] = {}
    for path, entry in entries.items():
        normalized_key = _portable_entry_key(path)
        if normalized_key in normalized_keys or path in forbidden_entry_names:
            raise ValueError(f"Duplicate or forbidden embedded entry path: {path}")
        normalized_keys.add(normalized_key)
        if not isinstance(entry, dict) or not ENTRY_REQUIRED_FIELDS <= set(entry):
            raise ValueError(f"Embedded entry fields are missing: {path}")
        if set(entry) - ENTRY_REQUIRED_FIELDS - ENTRY_OPTIONAL_FIELDS:
            raise ValueError(f"Unexpected embedded entry fields: {path}")
        if (
            entry.get("kind") not in {"html", "file"}
            or not isinstance(entry.get("title"), str)
            or not isinstance(entry.get("mime"), str)
            or not isinstance(entry.get("needs_plotly"), bool)
            or (
                "opaque_standalone" in entry
                and not isinstance(entry.get("opaque_standalone"), bool)
            )
        ):
            raise ValueError(f"Embedded entry types are invalid: {path}")
        source_bytes = _strict_non_negative_int(
            entry.get("source_bytes"),
            label=f"{path}.source_bytes",
            limit=MAX_ENTRY_BYTES,
        )
        embedded_bytes = _strict_non_negative_int(
            entry.get("embedded_bytes"),
            label=f"{path}.embedded_bytes",
            limit=MAX_ENTRY_BYTES,
        )
        _validate_sha(entry.get("source_sha256"), label=f"{path}.source_sha256")
        _validate_sha(entry.get("embedded_sha256"), label=f"{path}.embedded_sha256")
        total_declared_bytes += embedded_bytes
        if total_declared_bytes > MAX_TOTAL_ENTRY_BYTES:
            raise ValueError("Total embedded byte budget exceeded")
        decoded = _decoded_entry(entry, label=str(path))
        decoded_entries[path] = decoded
        if entry.get("kind") == "html":
            html_count += int(path != INVENTORY_PATH)
            try:
                decoded_document = decoded.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"Embedded HTML is not UTF-8: {path}") from error
            marker_opaque = _is_opaque_standalone(decoded_document)
            declared_opaque = bool(entry.get("opaque_standalone"))
            if declared_opaque or marker_opaque:
                if hardened and not declared_opaque:
                    raise ValueError(f"Opaque standalone flag is missing: {path}")
                opaque_count += 1
                if not marker_opaque:
                    raise ValueError(f"Opaque standalone contract missing: {path}")
                _validate_single_html_document(
                    decoded_document,
                    label=f"{label}:{path}",
                    opaque_depth=opaque_depth + 1,
                )
                if (
                    source_bytes != embedded_bytes
                    or entry.get("source_sha256") != entry.get("embedded_sha256")
                ):
                    raise ValueError(f"Opaque standalone was modified: {path}")
            else:
                if any(
                    marker in decoded_document
                    for marker in (
                        "const files = ",
                        "const plotlyBundle = ",
                        "const metadata = ",
                        "window.ETUDECAS_SINGLE_HTML",
                    )
                ):
                    raise ValueError(f"Incomplete opaque standalone markers: {path}")
                _validate_document_contract(
                    decoded_document,
                    label=f"{label}:{path}",
                    allow_local=False,
                )
                if decoded_document.count(FRAGMENT_TOKEN) != 1:
                    raise ValueError(f"Fragment bridge token count is invalid: {path}")
                expected_plotly_tokens = int(bool(entry.get("needs_plotly")))
                if decoded_document.count(PLOTLY_TOKEN) != expected_plotly_tokens:
                    raise ValueError(f"Plotly bridge token count is invalid: {path}")
                if hardened:
                    _assert_csp(decoded_document, SINGLE_CSP_POLICY, label=str(path))
        else:
            basename = unicodedata.normalize("NFC", PurePosixPath(path).name).casefold()
            if basename in download_names:
                raise ValueError(f"Ambiguous download basename: {path}")
            download_names.add(basename)

    declared_view_count = _strict_non_negative_int(
        metadata.get("view_count"),
        label="view_count",
        limit=MAX_ENTRY_COUNT,
    )
    if declared_view_count != html_count:
        raise ValueError("Embedded view count mismatch")
    declared_opaque_count = metadata.get("opaque_standalone_view_count")
    if declared_opaque_count is not None and _strict_non_negative_int(
        declared_opaque_count,
        label="opaque_standalone_view_count",
        limit=MAX_ENTRY_COUNT,
    ) != opaque_count:
        raise ValueError("Opaque standalone view count mismatch")
    if INVENTORY_PATH not in entries or entries[INVENTORY_PATH].get("kind") != "html":
        raise ValueError("Exact embedded inventory is missing")
    expected_inventory = inventory_document(
        {path: entry for path, entry in entries.items() if path != INVENTORY_PATH},
        str(metadata["source_package"]),
        hardened=hardened,
    ).encode("utf-8")
    if decoded_entries[INVENTORY_PATH] != expected_inventory:
        raise ValueError("Embedded inventory content is not exact")

    declared_plotly_embedded = metadata.get("plotly_embedded")
    if declared_plotly_embedded is not None and not isinstance(
        declared_plotly_embedded,
        bool,
    ):
        raise ValueError("Plotly embedded flag is invalid")
    plotly_embedded = (
        bool(declared_plotly_embedded)
        if declared_plotly_embedded is not None
        else bool(metadata.get("plotly_source_sha256"))
    )
    if set(plotly_entry) != PLOTLY_FIELDS:
        raise ValueError("Plotly runtime entry fields are invalid")
    plotly_source_bytes = _strict_non_negative_int(
        plotly_entry.get("source_bytes"),
        label="plotly.source_bytes",
        limit=MAX_ENTRY_BYTES,
    )
    plotly_source_sha = _validate_sha(
        plotly_entry.get("source_sha256"),
        label="plotly.source_sha256",
    )
    plotly_embedded_sha = _validate_sha(
        plotly_entry.get("embedded_sha256"),
        label="plotly.embedded_sha256",
    )
    plotly_decoded = _decoded_entry(plotly_entry, label="plotly")
    if plotly_embedded:
        if (
            not plotly_decoded
            or len(plotly_decoded) != plotly_source_bytes
            or plotly_source_sha != plotly_embedded_sha
            or plotly_source_sha != metadata.get("plotly_source_sha256")
        ):
            raise ValueError("Embedded Plotly bundle is invalid")
    elif (
        plotly_decoded
        or plotly_source_bytes
        or metadata.get("plotly_source_sha256")
        or plotly_source_sha != sha256_bytes(b"")
        or plotly_embedded_sha != sha256_bytes(b"")
    ):
        raise ValueError("Unused Plotly bundle must not be embedded")
    return metadata


def validate_single_html(output_html: Path) -> dict[str, object]:
    output_html = output_html.resolve()
    if output_html.stat().st_size > MAX_SINGLE_HTML_BYTES:
        raise ValueError(f"Single HTML exceeds its size budget: {output_html}")
    try:
        document = output_html.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Single HTML is not valid UTF-8: {output_html}") from error
    metadata = _validate_single_html_document(
        document,
        label=str(output_html),
        opaque_depth=0,
    )
    return {
        **metadata,
        "output_html": str(output_html),
        "output_bytes": output_html.stat().st_size,
        "output_sha256": sha256_file(output_html),
    }


def build_single_html(
    source_dir: Path,
    output_html: Path,
    *,
    index_aliases: Iterable[str] = (),
) -> dict[str, object]:
    source_dir = source_dir.resolve()
    output_html = output_html.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source package not found: {source_dir}")
    if not (source_dir / "index.html").is_file():
        raise FileNotFoundError(f"Source index not found: {source_dir / 'index.html'}")
    hash_path = output_html.with_suffix(output_html.suffix + ".sha256.txt")
    existing_outputs = [path for path in (output_html, hash_path) if path.exists()]
    if existing_outputs:
        raise FileExistsError(
            "Single HTML output already exists: "
            + ", ".join(str(path) for path in existing_outputs)
        )
    if output_html.suffix.lower() != ".html":
        raise ValueError("Output must have an .html suffix")
    if output_html == source_dir / "index.html" or source_dir in output_html.parents:
        raise ValueError("Output HTML must be outside the source package")

    explicit_aliases = {
        str(value).strip() for value in index_aliases if str(value).strip()
    }
    normalized_aliases: set[str] = set()
    for alias in explicit_aliases:
        normalized_alias = _portable_entry_key(alias)
        if (
            PurePosixPath(alias).name != alias
            or not alias.lower().endswith(".html")
            or alias in {"index.html", INVENTORY_PATH}
            or normalized_alias in normalized_aliases
        ):
            raise ValueError(f"Index alias must be a root HTML filename: {alias}")
        normalized_aliases.add(normalized_alias)
        if not (source_dir / alias).is_file():
            raise FileNotFoundError(f"Index alias not found: {source_dir / alias}")
    index_names = set(INDEX_NAMES) | explicit_aliases

    source_files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    relative_paths = {path.relative_to(source_dir).as_posix() for path in source_files}
    if INVENTORY_PATH in relative_paths:
        raise ValueError(f"Reserved inventory source is forbidden: {INVENTORY_PATH}")
    if len(source_files) + 1 > MAX_ENTRY_COUNT:
        raise ValueError("Source package contains too many files")
    normalized_paths: set[str] = set()
    source_total_bytes = 0
    for source in source_files:
        relative = source.relative_to(source_dir).as_posix()
        normalized = _portable_entry_key(relative)
        if normalized in normalized_paths:
            raise ValueError(f"Case or Unicode-colliding source path: {relative}")
        normalized_paths.add(normalized)
        if any(marker in relative for marker in RESERVED_SOURCE_MARKERS):
            raise ValueError(f"Reserved standalone marker found in source path: {relative}")
        size = source.stat().st_size
        if size > MAX_ENTRY_BYTES:
            raise ValueError(f"Source file exceeds the per-entry budget: {relative}")
        source_total_bytes += size
        if source_total_bytes > MAX_TOTAL_ENTRY_BYTES:
            raise ValueError("Source package exceeds the total byte budget")
    index_bytes = (source_dir / "index.html").read_bytes()
    for alias in index_names - {"index.html"}:
        alias_path = source_dir / alias
        if alias_path.is_file() and alias_path.read_bytes() != index_bytes:
            raise ValueError(f"Index alias differs from index.html: {alias}")

    download_basenames: set[str] = set()
    for relative in relative_paths - index_names - {PLOTLY_PATH}:
        if relative.lower().endswith(".html"):
            continue
        basename = unicodedata.normalize(
            "NFC",
            PurePosixPath(relative).name,
        ).casefold()
        if basename in download_basenames:
            raise ValueError(f"Ambiguous downloadable basename: {relative}")
        download_basenames.add(basename)
    known_paths = set(relative_paths)
    entries: dict[str, dict[str, object]] = {}
    for source in source_files:
        relative = source.relative_to(source_dir).as_posix()
        if relative in index_names or relative == PLOTLY_PATH:
            continue
        source_data = source.read_bytes()
        if relative.endswith(".html"):
            source_text = source_data.decode("utf-8")
            transformed, needs_plotly, opaque_standalone = transform_view(
                source_text,
                relative,
                source_dir,
                known_paths,
                index_names=index_names,
            )
            embedded_data = transformed.encode("utf-8")
            if len(embedded_data) > MAX_ENTRY_BYTES:
                raise ValueError(f"Transformed HTML exceeds the entry budget: {relative}")
            entries[relative] = _entry(
                relative,
                source_data,
                embedded_data,
                kind="html",
                title=extract_title(transformed, relative),
                needs_plotly=needs_plotly,
                opaque_standalone=opaque_standalone,
            )
        else:
            embedded_data = source_data
            if relative == "LISEZ_MOI.txt":
                embedded_data = (
                    "DEMONSTRATION SUPPLY CHAIN - FICHIER HTML UNIQUE\n\n"
                    "Double-cliquer sur le fichier HTML. Aucun ZIP, sous-dossier, serveur "
                    "ou acces Internet n'est necessaire. Utiliser un navigateur recent.\n"
                ).encode("utf-8")
            entries[relative] = _entry(
                relative,
                source_data,
                embedded_data,
                kind="file",
            )

    inventory = inventory_document(entries, source_dir.name).encode("utf-8")
    if sum(int(entry["embedded_bytes"]) for entry in entries.values()) + len(
        inventory
    ) > MAX_TOTAL_ENTRY_BYTES:
        raise ValueError("Embedded package exceeds the total byte budget")
    entries[INVENTORY_PATH] = _entry(
        INVENTORY_PATH,
        inventory,
        inventory,
        kind="html",
        title="Contenu embarqué",
    )

    index_source = index_bytes.decode("utf-8")
    _assert_no_reserved_source_markers(index_source, label="index.html")
    _validate_document_contract(index_source, label="index.html", allow_local=True)
    index_document = rewrite_local_links(
        index_source,
        "index.html",
        known_paths,
        index_names=index_names,
    )
    index_document = inline_local_sources(
        index_document,
        "index.html",
        source_dir,
        known_paths,
    )
    index_document = TITLE_RE.sub(
        "<title>Démonstration Supply Chain — HTML autonome</title>",
        index_document,
        count=1,
    )
    if "<body>" not in index_document or "</body>" not in index_document:
        raise ValueError("Source index must contain plain body tags")
    index_document = index_document.replace("<body>", "<body>" + SHELL_HTML, 1)
    index_document = _inject_csp(index_document, SINGLE_CSP_POLICY)

    needs_plotly = any(bool(entry.get("needs_plotly")) for entry in entries.values())
    plotly_path = source_dir / PLOTLY_PATH
    if needs_plotly and not plotly_path.is_file():
        raise FileNotFoundError(f"Local Plotly bundle not found: {plotly_path}")
    plotly_data = plotly_path.read_bytes() if needs_plotly else b""
    plotly_entry = {
        "source_bytes": len(plotly_data),
        "source_sha256": sha256_bytes(plotly_data),
        "embedded_sha256": sha256_bytes(plotly_data),
        "gzip_base64": gzip_base64(plotly_data),
    }
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_package": source_dir.name,
        "view_count": sum(entry["kind"] == "html" for entry in entries.values()) - 1,
        "embedded_entry_count": len(entries),
        "requires_internet": False,
        "requires_local_server": False,
        "plotly_embedded": needs_plotly,
        "plotly_source_sha256": plotly_entry["source_sha256"] if needs_plotly else "",
        "opaque_standalone_view_count": sum(
            bool(entry.get("opaque_standalone")) for entry in entries.values()
        ),
        "index_aliases": sorted(explicit_aliases),
        "security_profile": SECURITY_PROFILE,
        "max_entry_bytes": MAX_ENTRY_BYTES,
        "max_total_entry_bytes": MAX_TOTAL_ENTRY_BYTES,
        "opaque_max_depth": MAX_OPAQUE_DEPTH,
        "memory_budget_note": (
            "Entrées bornées et décompressées une par une; une vue opaque peut "
            "temporairement occuper plusieurs fois sa taille dans le navigateur."
        ),
    }
    runtime = (
        RUNTIME.replace("__EMBEDDED_FILES_JSON__", _script_json(entries))
        .replace("__PLOTLY_BUNDLE_JSON__", _script_json(plotly_entry))
        .replace("__STANDALONE_METADATA_JSON__", _script_json(metadata))
    )
    index_document = index_document.replace("</head>", SHELL_STYLE + "</head>", 1)
    index_document = index_document.replace("</body>", runtime + "</body>", 1)
    _validate_document_contract(index_document, label="single HTML shell", allow_local=False)
    if len(index_document.encode("utf-8")) > MAX_SINGLE_HTML_BYTES:
        raise ValueError("Generated single HTML exceeds its size budget")

    output_html.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        prefix=f".{output_html.name}.",
        suffix=".tmp",
        dir=output_html.parent,
    ) as stream:
        stream.write(index_document)
        temporary = Path(stream.name)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="ascii",
        delete=False,
        prefix=f".{hash_path.name}.",
        suffix=".tmp",
        dir=output_html.parent,
    ) as stream:
        temporary_hash = Path(stream.name)
    output_created = False
    hash_created = False
    try:
        validation = validate_single_html(temporary)
        output_hash = sha256_file(temporary)
        temporary_hash.write_text(
            f"{output_hash}  {output_html.name}\n",
            encoding="ascii",
        )
        if output_html.exists() or hash_path.exists():
            raise FileExistsError("Single HTML target appeared during the build")
        temporary.rename(output_html)
        output_created = True
        temporary_hash.rename(hash_path)
        hash_created = True
    except Exception:
        temporary.unlink(missing_ok=True)
        temporary_hash.unlink(missing_ok=True)
        if hash_created:
            hash_path.unlink(missing_ok=True)
        if output_created:
            output_html.unlink(missing_ok=True)
        raise
    return {
        **validation,
        "output_html": str(output_html),
        "output_bytes": output_html.stat().st_size,
        "output_sha256": output_hash,
        "hash_file": str(hash_path),
    }


def main() -> None:
    args = parse_args()
    result = build_single_html(
        args.source_dir,
        args.output_html,
        index_aliases=args.index_alias,
    )
    print(f"[OK] Single HTML: {result['output_html']}")
    print(f"[OK] Bytes: {result['output_bytes']}")
    print(f"[OK] SHA-256: {result['output_sha256']}")
    print(f"[OK] Embedded entries: {result['embedded_entry_count']}")
    print(f"[OK] Views: {result['view_count']}")


if __name__ == "__main__":
    main()
