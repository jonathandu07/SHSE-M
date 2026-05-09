# backend/modules/main/logs.py
# =============================================================================
# Analyseur et nettoyeur de logs — backend/logs
# =============================================================================
# Rôle :
# - analyser de manière approfondie les fichiers présents dans backend/logs ;
# - produire un diagnostic exploitable : gravité, erreurs récurrentes, traces Python,
#   activité temporelle, fichiers suspects, logs obsolètes ;
# - supprimer les logs obsolètes selon des règles prudentes et paramétrables.
#
# Sécurité :
# - suppression limitée au dossier de logs résolu ;
# - aucun suivi de symlink ;
# - mode CLI en simulation par défaut ; utiliser --apply pour supprimer réellement ;
# - les fichiers actifs récents ne sont jamais supprimés par défaut.
# =============================================================================

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import time
import traceback
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Constantes / chemins
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "logs.py"

# backend/modules/main/logs.py -> backend = parents[2]
try:
    _BACKEND_ROOT = _THIS_FILE.parents[2]
except Exception:
    _BACKEND_ROOT = Path.cwd() / "backend"

DEFAULT_LOG_DIR = _BACKEND_ROOT / "logs"
DEFAULT_REPORT_PATH = DEFAULT_LOG_DIR / "diagnostic_logs.json"

LOG_EXTENSIONS = {
    ".log",
    ".txt",
    ".out",
    ".err",
    ".jsonl",
    ".json",
    ".csv",
    ".gz",
    ".old",
    ".bak",
}

ROTATED_SUFFIX_PATTERNS = (
    re.compile(r"\.log\.\d+$", re.IGNORECASE),
    re.compile(r"\.txt\.\d+$", re.IGNORECASE),
    re.compile(r"\.out\.\d+$", re.IGNORECASE),
    re.compile(r"\.err\.\d+$", re.IGNORECASE),
    re.compile(r"\.(?:gz|zip|old|bak|backup)$", re.IGNORECASE),
    re.compile(r"\.\d{4}-\d{2}-\d{2}(?:[._-]\d+)?$", re.IGNORECASE),
)

LEVEL_ORDER = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "NOTICE": 25,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "EXCEPTION": 45,
    "CRITICAL": 50,
    "FATAL": 50,
}

CANONICAL_LEVEL = {
    "WARN": "WARNING",
    "FATAL": "CRITICAL",
}

SEVERITY_PATTERNS = [
    re.compile(r"\b(CRITICAL|FATAL|ERROR|EXCEPTION|WARNING|WARN|INFO|DEBUG|TRACE|NOTICE)\b", re.IGNORECASE),
    re.compile(r"\[(CRITICAL|FATAL|ERROR|EXCEPTION|WARNING|WARN|INFO|DEBUG|TRACE|NOTICE)\]", re.IGNORECASE),
]

TIMESTAMP_PATTERNS = [
    # 2026-05-09 14:30:22,123 / 2026-05-09T14:30:22.123Z
    re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?)"
    ),
    # 09/May/2026 14:30:22 / 09-May-2026 14:30:22
    re.compile(r"(?P<ts>\d{1,2}[/-][A-Za-z]{3}[/-]\d{4}:?\s+\d{2}:\d{2}:\d{2})"),
    # Django/Python compact : 09/05/2026 14:30:22
    re.compile(r"(?P<ts>\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}:\d{2})"),
    # Syslog : May 09 14:30:22
    re.compile(r"(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"),
]

SOURCE_PATTERNS = [
    # 2026-... ERROR django.request: message
    re.compile(r"\b(?:TRACE|DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|EXCEPTION|CRITICAL|FATAL)\s+(?P<src>[A-Za-z_][\w.:-]{2,})\s*[:\-]"),
    # [django.request] ERROR message
    re.compile(r"\[(?P<src>[A-Za-z_][\w.:-]{2,})\]\s*(?:TRACE|DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|EXCEPTION|CRITICAL|FATAL)\b"),
    # logger=name
    re.compile(r"\blogger=(?P<src>[A-Za-z_][\w.:-]{2,})\b"),
    re.compile(r"\bmodule=(?P<src>[A-Za-z_][\w.:-]{2,})\b"),
]

TRACEBACK_START = "Traceback (most recent call last):"
PYTHON_FILE_RE = re.compile(r'^\s*File "(?P<file>.+?)", line (?P<line>\d+), in (?P<func>.+)$')
PYTHON_EXCEPTION_RE = re.compile(r"^\s*(?P<exc>[A-Za-z_][\w.]*Error|[A-Za-z_][\w.]*Exception|KeyboardInterrupt|SystemExit)(?::\s*(?P<msg>.*))?$")
HTTP_STATUS_RE = re.compile(r"\b(?P<status>[1-5]\d{2})\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
HEX_RE = re.compile(r"\b0x[0-9a-f]+\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/)[^\s:;,]+")


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class LogEntry:
    file: str
    line_no: int
    level: str
    message: str
    timestamp: Optional[str] = None
    source: Optional[str] = None
    exception_type: Optional[str] = None
    http_status: Optional[int] = None


@dataclass
class StackTraceDiagnostic:
    file: str
    start_line: int
    exception_type: Optional[str] = None
    message: Optional[str] = None
    frames: List[Dict[str, Any]] = field(default_factory=list)
    excerpt: List[str] = field(default_factory=list)


@dataclass
class FileDiagnostic:
    path: str
    relative_path: str
    size_bytes: int
    modified_at: str
    age_days: float
    is_rotated: bool
    is_empty: bool
    is_binary_like: bool
    encoding_used: str
    line_count: int = 0
    parsed_entries: int = 0
    timestamped_entries: int = 0
    malformed_lines: int = 0
    levels: Dict[str, int] = field(default_factory=dict)
    sources: Dict[str, int] = field(default_factory=dict)
    http_statuses: Dict[str, int] = field(default_factory=dict)
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    stack_traces_count: int = 0
    top_repeated_messages: List[Dict[str, Any]] = field(default_factory=list)
    error_samples: List[Dict[str, Any]] = field(default_factory=list)
    stack_traces: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    read_error: Optional[str] = None


@dataclass
class CleanupRule:
    keep_days: int = 30
    rotated_keep_days: int = 14
    delete_empty_after_days: int = 2
    max_total_size_mb: Optional[float] = None
    keep_latest_files: int = 5
    include_extensions: Tuple[str, ...] = tuple(sorted(LOG_EXTENSIONS))


@dataclass
class CleanupCandidate:
    path: str
    relative_path: str
    reason: str
    size_bytes: int
    age_days: float
    action: str = "would_delete"
    error: Optional[str] = None


@dataclass
class LogsReport:
    meta: Dict[str, Any]
    summary: Dict[str, Any]
    diagnostic: Dict[str, Any]
    files: List[Dict[str, Any]]
    cleanup: Dict[str, Any]
    inconnues: Dict[str, List[Dict[str, str]]]
    alertes: Dict[str, List[Dict[str, str]]]


# =============================================================================
# Helpers généraux
# =============================================================================


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _iso(dt: _dt.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc).isoformat()


def _safe_float(x: Any) -> Optional[float]:
    try:
        value = float(x)
    except Exception:
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, Counter):
        return dict(value)
    return str(value)


def _push_item(report: Dict[str, Any], section: str, category: str, nom: str, detail: str) -> None:
    report.setdefault(section, {}).setdefault(category, []).append({"nom": str(nom), "detail": str(detail)})


def _push_inconnue(report: Dict[str, Any], category: str, nom: str, raison: str) -> None:
    report.setdefault("inconnues", {}).setdefault(category, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_dict_list(items: Iterable[Mapping[str, Any]], keys: Sequence[str]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        sig = tuple(str(item.get(k, "")) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(item))
    return out


def _dedup_report(report: Dict[str, Any]) -> None:
    for section, keys in (("inconnues", ("nom", "raison")), ("alertes", ("nom", "detail"))):
        bloc = report.setdefault(section, {})
        for category, items in list(bloc.items()):
            bloc[category] = _dedup_dict_list(list(items or []), keys)


def _is_inside(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _sha256_file(path: Path, *, max_bytes: int = 1_048_576) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max_bytes
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def _is_binary_sample(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    # ratio de caractères de contrôle hors \t\n\r
    control = sum(1 for b in data if b < 32 and b not in (9, 10, 13))
    return (control / max(len(data), 1)) > 0.05


def _decode_line(raw: bytes, preferred_encoding: str = "utf-8") -> Tuple[str, str]:
    for enc in (preferred_encoding, "utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def _open_maybe_gzip(path: Path) -> Iterator[bytes]:
    if path.suffix.lower() == ".gz":
        with gzip.open(path, "rb") as f:
            for line in f:
                yield line
    else:
        with path.open("rb") as f:
            for line in f:
                yield line


def _iter_log_files(log_dir: Path, include_extensions: Sequence[str]) -> List[Path]:
    include = {ext.lower() for ext in include_extensions}
    if not log_dir.exists():
        return []

    paths: List[Path] = []
    for path in log_dir.rglob("*"):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            lower_name = path.name.lower()
            suffix = path.suffix.lower()
            if suffix in include or any(p.search(lower_name) for p in ROTATED_SUFFIX_PATTERNS):
                paths.append(path)
        except OSError:
            continue
    return sorted(paths, key=lambda p: str(p).lower())


def _is_rotated_file(path: Path) -> bool:
    name = path.name.lower()
    if any(p.search(name) for p in ROTATED_SUFFIX_PATTERNS):
        return True
    # app.log.2026-05-09, app.log.old, app.log.gz
    return any(part.isdigit() for part in path.suffixes[1:])


def _normalize_message(message: str) -> str:
    msg = message.strip()
    msg = UUID_RE.sub("<uuid>", msg)
    msg = IP_RE.sub("<ip>", msg)
    msg = HEX_RE.sub("<hex>", msg)
    msg = PATH_RE.sub("<path>", msg)
    msg = NUMBER_RE.sub("<num>", msg)
    msg = re.sub(r"\s+", " ", msg)
    return msg[:500]


def _detect_level(line: str) -> str:
    for pattern in SEVERITY_PATTERNS:
        m = pattern.search(line)
        if m:
            raw = m.group(1).upper()
            return CANONICAL_LEVEL.get(raw, raw)
    if TRACEBACK_START in line:
        return "EXCEPTION"
    if "Exception" in line or "Error:" in line:
        return "ERROR"
    return "UNKNOWN"


def _detect_source(line: str) -> Optional[str]:
    for pattern in SOURCE_PATTERNS:
        m = pattern.search(line)
        if m:
            return m.group("src")
    return None


def _parse_timestamp(ts_raw: str) -> Optional[_dt.datetime]:
    text = ts_raw.strip().replace(",", ".")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    candidates = [
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%b/%Y %H:%M:%S",
        "%d-%b-%Y %H:%M:%S",
        "%d/%b/%Y:%H:%M:%S",
        "%d-%b-%Y:%H:%M:%S",
        "%b %d %H:%M:%S",
    ]

    current_year = _now_utc().year
    for fmt in candidates:
        try:
            dt = _dt.datetime.strptime(text, fmt)
            if "%Y" not in fmt:
                dt = dt.replace(year=current_year)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            return dt.astimezone(_dt.timezone.utc)
        except Exception:
            continue

    try:
        dt = _dt.datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt.astimezone(_dt.timezone.utc)
    except Exception:
        return None


def _detect_timestamp(line: str) -> Tuple[Optional[str], Optional[_dt.datetime]]:
    for pattern in TIMESTAMP_PATTERNS:
        m = pattern.search(line)
        if m:
            raw = m.group("ts")
            return raw, _parse_timestamp(raw)
    return None, None


def _detect_http_status(line: str) -> Optional[int]:
    m = HTTP_STATUS_RE.search(line)
    if not m:
        return None
    try:
        status = int(m.group("status"))
    except Exception:
        return None
    return status if 100 <= status <= 599 else None


def _detect_exception_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    m = PYTHON_EXCEPTION_RE.match(line.strip())
    if not m:
        return None, None
    return m.group("exc"), m.group("msg")


def _looks_like_new_entry(line: str) -> bool:
    ts, _ = _detect_timestamp(line)
    if ts is not None:
        return True
    level = _detect_level(line)
    return level != "UNKNOWN" and not line.startswith((" ", "\t"))


def _severity_value(level: str) -> int:
    return LEVEL_ORDER.get(level.upper(), 0)


# =============================================================================
# Analyse d'un fichier
# =============================================================================


def _analyse_stack_traces(relative_path: str, lines: Sequence[Tuple[int, str]], *, max_stack_traces: int = 10) -> List[StackTraceDiagnostic]:
    traces: List[StackTraceDiagnostic] = []
    i = 0
    while i < len(lines):
        line_no, text = lines[i]
        if TRACEBACK_START not in text:
            i += 1
            continue

        excerpt: List[str] = [text.rstrip("\n")[:500]]
        frames: List[Dict[str, Any]] = []
        exception_type: Optional[str] = None
        exception_msg: Optional[str] = None
        j = i + 1

        while j < len(lines):
            ln, t = lines[j]
            if j > i + 1 and _looks_like_new_entry(t) and TRACEBACK_START not in t:
                break
            clean = t.rstrip("\n")
            if len(excerpt) < 25:
                excerpt.append(clean[:500])

            fm = PYTHON_FILE_RE.match(clean)
            if fm:
                frames.append({
                    "file": fm.group("file"),
                    "line": int(fm.group("line")),
                    "function": fm.group("func"),
                })

            exc, msg = _detect_exception_line(clean)
            if exc:
                exception_type = exc
                exception_msg = msg
            j += 1

        traces.append(StackTraceDiagnostic(
            file=relative_path,
            start_line=line_no,
            exception_type=exception_type,
            message=exception_msg,
            frames=frames[-10:],
            excerpt=excerpt,
        ))
        if len(traces) >= max_stack_traces:
            break
        i = max(j, i + 1)

    return traces


def analyser_fichier_log(
    path: Path,
    *,
    log_dir: Path,
    now: Optional[_dt.datetime] = None,
    max_error_samples: int = 10,
    max_repeated_messages: int = 15,
    max_stack_traces: int = 10,
    max_lines: Optional[int] = None,
    preferred_encoding: str = "utf-8",
) -> FileDiagnostic:
    now = now or _now_utc()
    stat = path.stat()
    age_days = max(0.0, (now.timestamp() - stat.st_mtime) / 86400.0)
    relative_path = str(path.resolve().relative_to(log_dir.resolve())) if _is_inside(log_dir, path) else path.name

    sample = b""
    try:
        with path.open("rb") as f:
            sample = f.read(4096)
    except Exception:
        pass

    binary_like = _is_binary_sample(sample)
    diag = FileDiagnostic(
        path=str(path),
        relative_path=relative_path,
        size_bytes=stat.st_size,
        modified_at=_iso(_dt.datetime.fromtimestamp(stat.st_mtime, tz=_dt.timezone.utc)),
        age_days=round(age_days, 3),
        is_rotated=_is_rotated_file(path),
        is_empty=stat.st_size == 0,
        is_binary_like=binary_like,
        encoding_used=preferred_encoding,
    )

    if stat.st_size == 0:
        diag.anomalies.append("fichier_vide")
        return diag

    if binary_like and path.suffix.lower() != ".gz":
        diag.anomalies.append("fichier_probablement_binaire")
        return diag

    level_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    normalized_counter: Counter[str] = Counter()
    error_samples: Deque[Dict[str, Any]] = deque(maxlen=max_error_samples)
    timestamp_values: List[_dt.datetime] = []
    timestamped_entries = 0
    parsed_entries = 0
    malformed_lines = 0
    line_count = 0
    encoding_counter: Counter[str] = Counter()
    recent_lines: List[Tuple[int, str]] = []

    try:
        for raw in _open_maybe_gzip(path):
            line_count += 1
            if max_lines is not None and line_count > max_lines:
                diag.anomalies.append(f"analyse_limitee_a_{max_lines}_lignes")
                break

            line, enc = _decode_line(raw, preferred_encoding=preferred_encoding)
            encoding_counter[enc] += 1
            if "\ufffd" in line:
                malformed_lines += 1

            if len(recent_lines) < 200_000:
                recent_lines.append((line_count, line))

            stripped = line.strip("\n")
            if not stripped.strip():
                continue

            timestamp_raw, timestamp_dt = _detect_timestamp(stripped)
            level = _detect_level(stripped)
            source = _detect_source(stripped)
            status = _detect_http_status(stripped)
            exception_type, exception_msg = _detect_exception_line(stripped)

            if timestamp_dt is not None:
                timestamped_entries += 1
                timestamp_values.append(timestamp_dt)

            if level != "UNKNOWN" or timestamp_raw is not None or source is not None:
                parsed_entries += 1

            level_counter[level] += 1
            if source:
                source_counter[source] += 1
            if status is not None:
                status_counter[str(status)] += 1

            if _severity_value(level) >= LEVEL_ORDER["WARNING"] or exception_type or (status is not None and status >= 400):
                normalized_counter[_normalize_message(stripped)] += 1
                if len(error_samples) < max_error_samples:
                    error_samples.append({
                        "line": line_count,
                        "level": level,
                        "timestamp": _iso(timestamp_dt) if timestamp_dt else timestamp_raw,
                        "source": source,
                        "http_status": status,
                        "exception_type": exception_type,
                        "message": stripped[:600],
                    })
    except Exception as exc:
        diag.read_error = f"{type(exc).__name__}: {exc}"
        diag.anomalies.append("lecture_impossible")

    stack_traces = _analyse_stack_traces(relative_path, recent_lines, max_stack_traces=max_stack_traces)

    diag.line_count = line_count
    diag.parsed_entries = parsed_entries
    diag.timestamped_entries = timestamped_entries
    diag.malformed_lines = malformed_lines
    diag.levels = dict(level_counter.most_common())
    diag.sources = dict(source_counter.most_common(25))
    diag.http_statuses = dict(status_counter.most_common())
    diag.first_timestamp = _iso(min(timestamp_values)) if timestamp_values else None
    diag.last_timestamp = _iso(max(timestamp_values)) if timestamp_values else None
    diag.stack_traces_count = len(stack_traces)
    diag.stack_traces = [_to_jsonable(s) for s in stack_traces]
    diag.error_samples = list(error_samples)
    diag.encoding_used = encoding_counter.most_common(1)[0][0] if encoding_counter else preferred_encoding
    diag.top_repeated_messages = [
        {"count": count, "message_normalisee": msg}
        for msg, count in normalized_counter.most_common(max_repeated_messages)
        if count >= 2
    ]

    if line_count > 0 and timestamped_entries / line_count < 0.05:
        diag.anomalies.append("peu_de_timestamps_detectes")
    if malformed_lines > 0:
        diag.anomalies.append("lignes_avec_encodage_invalide")
    if level_counter.get("ERROR", 0) or level_counter.get("CRITICAL", 0) or level_counter.get("EXCEPTION", 0):
        diag.anomalies.append("erreurs_detectees")
    if stack_traces:
        diag.anomalies.append("tracebacks_python_detectes")
    if stat.st_size > 50 * 1024 * 1024:
        diag.anomalies.append("fichier_volumineux")

    return diag


# =============================================================================
# Nettoyage des logs obsolètes
# =============================================================================


def trouver_logs_obsoletes(
    log_dir: Path,
    files: Sequence[Path],
    *,
    rule: CleanupRule,
    now: Optional[_dt.datetime] = None,
) -> List[CleanupCandidate]:
    now = now or _now_utc()
    candidates: Dict[Path, CleanupCandidate] = {}

    protected_latest = set(
        sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)[: max(0, rule.keep_latest_files)]
    )

    def add(path: Path, reason: str) -> None:
        try:
            if path in protected_latest:
                return
            if path.is_symlink() or not path.is_file():
                return
            if not _is_inside(log_dir, path):
                return
            st = path.stat()
            age = max(0.0, (now.timestamp() - st.st_mtime) / 86400.0)
            candidates[path] = CleanupCandidate(
                path=str(path),
                relative_path=str(path.resolve().relative_to(log_dir.resolve())),
                reason=reason,
                size_bytes=st.st_size,
                age_days=round(age, 3),
            )
        except Exception:
            return

    for path in files:
        try:
            st = path.stat()
        except Exception:
            continue
        age = max(0.0, (now.timestamp() - st.st_mtime) / 86400.0)
        rotated = _is_rotated_file(path)

        if st.st_size == 0 and age >= rule.delete_empty_after_days:
            add(path, f"fichier vide depuis >= {rule.delete_empty_after_days} jours")
            continue

        if rotated and age >= rule.rotated_keep_days:
            add(path, f"log rotatif/archivé âgé de >= {rule.rotated_keep_days} jours")
            continue

        if age >= rule.keep_days:
            add(path, f"log âgé de >= {rule.keep_days} jours")

    # Limite de taille totale : supprimer les plus anciens jusqu'à revenir sous seuil.
    if rule.max_total_size_mb is not None and rule.max_total_size_mb >= 0:
        max_bytes = int(rule.max_total_size_mb * 1024 * 1024)
        sortable = []
        total = 0
        for path in files:
            try:
                st = path.stat()
            except Exception:
                continue
            total += st.st_size
            sortable.append((st.st_mtime, path, st.st_size))
        if total > max_bytes:
            for _, path, size in sorted(sortable, key=lambda it: it[0]):
                if total <= max_bytes:
                    break
                if path in protected_latest:
                    continue
                add(path, f"dépassement taille totale logs > {rule.max_total_size_mb} MB")
                total -= size

    return sorted(candidates.values(), key=lambda c: (c.age_days, c.relative_path), reverse=True)


def supprimer_logs_obsoletes(
    log_dir: str | os.PathLike[str] = DEFAULT_LOG_DIR,
    *,
    keep_days: int = 30,
    rotated_keep_days: int = 14,
    delete_empty_after_days: int = 2,
    max_total_size_mb: Optional[float] = None,
    keep_latest_files: int = 5,
    apply: bool = False,
    archive_before_delete: bool = False,
    archive_dir: Optional[str | os.PathLike[str]] = None,
    include_extensions: Sequence[str] = tuple(sorted(LOG_EXTENSIONS)),
) -> Dict[str, Any]:
    log_path = Path(log_dir).resolve()
    rule = CleanupRule(
        keep_days=int(keep_days),
        rotated_keep_days=int(rotated_keep_days),
        delete_empty_after_days=int(delete_empty_after_days),
        max_total_size_mb=max_total_size_mb,
        keep_latest_files=int(keep_latest_files),
        include_extensions=tuple(include_extensions),
    )

    cleanup: Dict[str, Any] = {
        "log_dir": str(log_path),
        "apply": bool(apply),
        "archive_before_delete": bool(archive_before_delete),
        "rules": _to_jsonable(rule),
        "candidates": [],
        "deleted": [],
        "archived": [],
        "errors": [],
        "bytes_reclaimable": 0,
        "bytes_deleted": 0,
    }

    if not log_path.exists():
        cleanup["errors"].append({"nom": "log_dir", "detail": "Le dossier de logs n'existe pas."})
        return cleanup
    if not log_path.is_dir():
        cleanup["errors"].append({"nom": "log_dir", "detail": "Le chemin de logs n'est pas un dossier."})
        return cleanup

    files = _iter_log_files(log_path, include_extensions)
    candidates = trouver_logs_obsoletes(log_path, files, rule=rule)
    cleanup["candidates"] = [_to_jsonable(c) for c in candidates]
    cleanup["bytes_reclaimable"] = sum(c.size_bytes for c in candidates)

    if not apply:
        return cleanup

    archive_path: Optional[Path] = None
    if archive_before_delete:
        archive_path = Path(archive_dir).resolve() if archive_dir else log_path / "archives_supprimes"
        archive_path.mkdir(parents=True, exist_ok=True)

    for candidate in candidates:
        path = Path(candidate.path)
        try:
            if not _is_inside(log_path, path):
                raise PermissionError("Refus : fichier hors du dossier de logs.")
            if path.is_symlink():
                raise PermissionError("Refus : suppression de symlink interdite.")
            if not path.exists():
                continue

            if archive_path is not None:
                rel = path.resolve().relative_to(log_path)
                dest = archive_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                cleanup["archived"].append({"source": str(path), "destination": str(dest)})

            size = path.stat().st_size
            path.unlink()
            cleanup["bytes_deleted"] += size
            cleanup["deleted"].append({**_to_jsonable(candidate), "action": "deleted"})
        except Exception as exc:
            cleanup["errors"].append({
                "path": str(path),
                "detail": f"{type(exc).__name__}: {exc}",
            })

    return cleanup


# =============================================================================
# Rapport global
# =============================================================================


def _build_global_diagnostic(files: Sequence[FileDiagnostic], cleanup: Dict[str, Any]) -> Dict[str, Any]:
    total_errors = sum(f.levels.get("ERROR", 0) + f.levels.get("EXCEPTION", 0) for f in files)
    total_critical = sum(f.levels.get("CRITICAL", 0) for f in files)
    total_warnings = sum(f.levels.get("WARNING", 0) for f in files)
    total_tracebacks = sum(f.stack_traces_count for f in files)
    binary_count = sum(1 for f in files if f.is_binary_like)
    malformed_count = sum(1 for f in files if f.malformed_lines > 0)
    obsolete_count = len(cleanup.get("candidates", []) or [])

    findings: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    if total_critical:
        findings.append({"gravite": "critique", "nom": "critical_logs", "detail": f"{total_critical} événement(s) CRITICAL/FATAL détecté(s)."})
        recommendations.append("Traiter en priorité les fichiers contenant CRITICAL/FATAL et les tracebacks associés.")
    if total_errors:
        findings.append({"gravite": "erreur", "nom": "error_logs", "detail": f"{total_errors} erreur(s)/exception(s) détectée(s)."})
        recommendations.append("Regrouper les erreurs récurrentes par message normalisé et corriger la cause racine avant de purger les logs récents.")
    if total_tracebacks:
        findings.append({"gravite": "erreur", "nom": "tracebacks_python", "detail": f"{total_tracebacks} traceback(s) Python détecté(s)."})
        recommendations.append("Examiner les derniers frames des tracebacks pour identifier le module exact à corriger.")
    if total_warnings:
        findings.append({"gravite": "avertissement", "nom": "warnings", "detail": f"{total_warnings} warning(s) détecté(s)."})
    if binary_count:
        findings.append({"gravite": "avertissement", "nom": "binary_like_files", "detail": f"{binary_count} fichier(s) probablement binaire(s) dans les logs."})
        recommendations.append("Vérifier que seuls des fichiers de logs texte sont écrits dans backend/logs.")
    if malformed_count:
        findings.append({"gravite": "avertissement", "nom": "encoding", "detail": f"{malformed_count} fichier(s) contiennent des caractères d'encodage invalides."})
    if obsolete_count:
        findings.append({"gravite": "info", "nom": "obsolete_logs", "detail": f"{obsolete_count} fichier(s) candidat(s) au nettoyage."})
        recommendations.append("Lancer avec --apply après vérification du rapport pour supprimer les fichiers obsolètes.")

    if total_critical or total_tracebacks:
        status = "critique"
    elif total_errors or binary_count or malformed_count:
        status = "attention"
    else:
        status = "sain"

    if not findings:
        findings.append({"gravite": "info", "nom": "aucune_anomalie_majeure", "detail": "Aucune anomalie significative détectée."})

    if not recommendations:
        recommendations.append("Conserver une rotation régulière des logs et exporter ce diagnostic lors des déploiements.")

    return {
        "status": status,
        "findings": findings,
        "recommendations": recommendations,
    }


def analyser_logs(
    log_dir: str | os.PathLike[str] = DEFAULT_LOG_DIR,
    *,
    keep_days: int = 30,
    rotated_keep_days: int = 14,
    delete_empty_after_days: int = 2,
    max_total_size_mb: Optional[float] = None,
    keep_latest_files: int = 5,
    include_extensions: Sequence[str] = tuple(sorted(LOG_EXTENSIONS)),
    max_lines_per_file: Optional[int] = None,
    cleanup_apply: bool = False,
    archive_before_delete: bool = False,
    archive_dir: Optional[str | os.PathLike[str]] = None,
    max_error_samples: int = 10,
    max_stack_traces: int = 10,
) -> Dict[str, Any]:
    log_path = Path(log_dir).resolve()
    now = _now_utc()
    report: Dict[str, Any] = {
        "meta": {
            "script": "backend.modules.main.logs",
            "generated_at": _iso(now),
            "log_dir": str(log_path),
            "mode": "analyse_diagnostic_nettoyage_logs",
            "cleanup_apply": bool(cleanup_apply),
        },
        "summary": {},
        "diagnostic": {},
        "files": [],
        "cleanup": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {"logs": [], "nettoyage": []},
    }

    if not log_path.exists():
        _push_inconnue(report, "impossibles", "backend/logs", "Le dossier de logs n'existe pas.")
        report["summary"] = {
            "files_count": 0,
            "total_size_bytes": 0,
            "levels": {},
        }
        report["diagnostic"] = {
            "status": "attention",
            "findings": [{"gravite": "avertissement", "nom": "log_dir_absent", "detail": "Aucun dossier backend/logs trouvé."}],
            "recommendations": ["Créer backend/logs ou configurer LOG_DIR vers le dossier réel."],
        }
        _dedup_report(report)
        return report

    if not log_path.is_dir():
        _push_inconnue(report, "impossibles", "backend/logs", "Le chemin fourni n'est pas un dossier.")
        _dedup_report(report)
        return report

    files = _iter_log_files(log_path, include_extensions)
    if not files:
        _push_inconnue(report, "partielles", "fichiers logs", "Aucun fichier de log reconnu dans le dossier.")

    diagnostics: List[FileDiagnostic] = []
    for path in files:
        try:
            diagnostics.append(
                analyser_fichier_log(
                    path,
                    log_dir=log_path,
                    now=now,
                    max_error_samples=max_error_samples,
                    max_stack_traces=max_stack_traces,
                    max_lines=max_lines_per_file,
                )
            )
        except Exception as exc:
            try:
                rel = str(path.resolve().relative_to(log_path.resolve()))
            except Exception:
                rel = path.name
            diagnostics.append(FileDiagnostic(
                path=str(path),
                relative_path=rel,
                size_bytes=path.stat().st_size if path.exists() else 0,
                modified_at=_iso(_dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.timezone.utc)) if path.exists() else _iso(now),
                age_days=0.0,
                is_rotated=_is_rotated_file(path),
                is_empty=False,
                is_binary_like=False,
                encoding_used="unknown",
                read_error=f"{type(exc).__name__}: {exc}",
                anomalies=["analyse_fichier_impossible"],
            ))
            report["alertes"]["logs"].append({"nom": rel, "detail": traceback.format_exc(limit=3)})

    cleanup = supprimer_logs_obsoletes(
        log_path,
        keep_days=keep_days,
        rotated_keep_days=rotated_keep_days,
        delete_empty_after_days=delete_empty_after_days,
        max_total_size_mb=max_total_size_mb,
        keep_latest_files=keep_latest_files,
        apply=cleanup_apply,
        archive_before_delete=archive_before_delete,
        archive_dir=archive_dir,
        include_extensions=include_extensions,
    )

    total_size = sum(f.size_bytes for f in diagnostics)
    total_lines = sum(f.line_count for f in diagnostics)
    level_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    anomalies_counter: Counter[str] = Counter()

    for f in diagnostics:
        level_counter.update(f.levels)
        source_counter.update(f.sources)
        status_counter.update(f.http_statuses)
        anomalies_counter.update(f.anomalies)

    report["files"] = [_to_jsonable(f) for f in diagnostics]
    report["cleanup"] = cleanup
    report["summary"] = {
        "files_count": len(diagnostics),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 3),
        "total_lines": total_lines,
        "levels": dict(level_counter.most_common()),
        "top_sources": dict(source_counter.most_common(20)),
        "http_statuses": dict(status_counter.most_common()),
        "anomalies": dict(anomalies_counter.most_common()),
        "stack_traces_count": sum(f.stack_traces_count for f in diagnostics),
        "obsolete_candidates_count": len(cleanup.get("candidates", []) or []),
        "bytes_reclaimable": cleanup.get("bytes_reclaimable", 0),
        "bytes_deleted": cleanup.get("bytes_deleted", 0),
    }
    report["diagnostic"] = _build_global_diagnostic(diagnostics, cleanup)

    for f in diagnostics:
        if f.read_error:
            report["alertes"]["logs"].append({"nom": f.relative_path, "detail": f.read_error})
        for anomaly in f.anomalies:
            if anomaly in {"erreurs_detectees", "tracebacks_python_detectes", "fichier_probablement_binaire"}:
                report["alertes"]["logs"].append({"nom": f.relative_path, "detail": anomaly})

    for err in cleanup.get("errors", []) or []:
        if isinstance(err, dict):
            report["alertes"]["nettoyage"].append({"nom": str(err.get("path", err.get("nom", "nettoyage"))), "detail": str(err.get("detail", err))})

    _dedup_report(report)
    return report


def analyser_et_nettoyer_logs(
    log_dir: str | os.PathLike[str] = DEFAULT_LOG_DIR,
    *,
    apply: bool = True,
    keep_days: int = 30,
    rotated_keep_days: int = 14,
    delete_empty_after_days: int = 2,
    max_total_size_mb: Optional[float] = None,
    keep_latest_files: int = 5,
    archive_before_delete: bool = False,
    archive_dir: Optional[str | os.PathLike[str]] = None,
    report_path: Optional[str | os.PathLike[str]] = None,
) -> Dict[str, Any]:
    """
    API principale appelée depuis le backend.

    Par défaut cette fonction applique bien le nettoyage, contrairement au CLI
    qui reste en simulation tant que --apply n'est pas fourni.
    """
    report = analyser_logs(
        log_dir,
        keep_days=keep_days,
        rotated_keep_days=rotated_keep_days,
        delete_empty_after_days=delete_empty_after_days,
        max_total_size_mb=max_total_size_mb,
        keep_latest_files=keep_latest_files,
        cleanup_apply=apply,
        archive_before_delete=archive_before_delete,
        archive_dir=archive_dir,
    )
    if report_path is not None:
        exporter_rapport_json(report, report_path)
    return report


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | os.PathLike[str] = DEFAULT_REPORT_PATH, *, indent: int = 2) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


# =============================================================================
# CLI
# =============================================================================


def _format_bytes(n: int | float) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TB"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse backend/logs, produit un diagnostic et nettoie les logs obsolètes."
    )
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="Dossier de logs à analyser. Défaut: backend/logs")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Chemin du rapport JSON généré.")
    parser.add_argument("--keep-days", type=int, default=30, help="Âge maximal des logs standards conservés.")
    parser.add_argument("--rotated-keep-days", type=int, default=14, help="Âge maximal des logs rotatifs/archivés conservés.")
    parser.add_argument("--delete-empty-after-days", type=int, default=2, help="Âge avant suppression des fichiers vides.")
    parser.add_argument("--max-total-size-mb", type=float, default=None, help="Taille totale maximale du dossier logs ; supprime les plus anciens si dépassée.")
    parser.add_argument("--keep-latest-files", type=int, default=5, help="Nombre de fichiers récents protégés contre suppression.")
    parser.add_argument("--max-lines-per-file", type=int, default=None, help="Limite d'analyse par fichier, utile si logs énormes.")
    parser.add_argument("--apply", action="store_true", help="Applique réellement la suppression. Sans ce flag : simulation.")
    parser.add_argument("--archive-before-delete", action="store_true", help="Copie les logs dans une archive locale avant suppression.")
    parser.add_argument("--archive-dir", default=None, help="Dossier d'archive si --archive-before-delete est utilisé.")
    parser.add_argument("--print-json", action="store_true", help="Affiche le rapport JSON complet dans stdout.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    report = analyser_logs(
        args.log_dir,
        keep_days=args.keep_days,
        rotated_keep_days=args.rotated_keep_days,
        delete_empty_after_days=args.delete_empty_after_days,
        max_total_size_mb=args.max_total_size_mb,
        keep_latest_files=args.keep_latest_files,
        max_lines_per_file=args.max_lines_per_file,
        cleanup_apply=args.apply,
        archive_before_delete=args.archive_before_delete,
        archive_dir=args.archive_dir,
    )
    out_path = exporter_rapport_json(report, args.report)

    if args.print_json:
        print(json.dumps(_to_jsonable(report), ensure_ascii=False, indent=2))
    else:
        summary = report.get("summary", {})
        diagnostic = report.get("diagnostic", {})
        cleanup = report.get("cleanup", {})
        print("=== Diagnostic logs backend ===")
        print(f"Dossier          : {report.get('meta', {}).get('log_dir')}")
        print(f"Statut           : {diagnostic.get('status')}")
        print(f"Fichiers         : {summary.get('files_count', 0)}")
        print(f"Taille totale    : {_format_bytes(summary.get('total_size_bytes', 0))}")
        print(f"Lignes analysées : {summary.get('total_lines', 0)}")
        print(f"Niveaux          : {summary.get('levels', {})}")
        print(f"Tracebacks       : {summary.get('stack_traces_count', 0)}")
        print(f"Candidats purge  : {summary.get('obsolete_candidates_count', 0)}")
        print(f"Récupérable      : {_format_bytes(summary.get('bytes_reclaimable', 0))}")
        print(f"Supprimé         : {_format_bytes(summary.get('bytes_deleted', 0))}")
        print(f"Mode suppression : {'APPLIQUÉ' if args.apply else 'SIMULATION'}")
        print(f"Rapport JSON     : {out_path}")
        if cleanup.get("errors"):
            print(f"Erreurs nettoyage: {len(cleanup.get('errors', []))}")

    # Code retour utile CI/CD.
    status = str(report.get("diagnostic", {}).get("status", "attention"))
    return 2 if status == "critique" else 1 if status == "attention" else 0


if __name__ == "__main__":
    raise SystemExit(main())
