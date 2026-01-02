# backend/logs.py
# -*- coding: utf-8 -*-
"""
Journalisation (logging) ultra détaillée pour debug.

Objectifs :
- Logs lisibles humainement (console) + logs persistants (fichiers) + fichier erreurs séparé
- Rotation automatique des fichiers (évite des logs gigantesques)
- Capture : warnings, exceptions non gérées (main thread + threads)
- Contexte riche : timestamp, niveau, process, thread, module, fonction, ligne, session_id
- Outils de debug : timer, décorateur de trace, dump sécurisé

USAGE RAPIDE (ex. dans backend/gui/main.py) :
------------------------------------------------
from backend.logs import setup_logging, get_logger, log_system_info

setup_logging(base_dir=BASE_DIR, app_name="shsem", level="DEBUG")
log_system_info()  # optionnel, utile au démarrage
log = get_logger(__name__)
log.info("GUI démarrée")

Ensuite dans ton code :
log.debug("val=%s", val)
try:
    ...
except Exception:
    log.exception("Erreur pendant ...")
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import logging
import logging.handlers
import os
import platform
import sys
import threading
import time
import traceback
import uuid
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple, Callable


# =========================
# Constantes / Defaults
# =========================
DEFAULT_APP_NAME = "app"
DEFAULT_LEVEL = "INFO"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 10
DEFAULT_ENCODING = "utf-8"

# Noms de fichiers
FILE_MAIN = "app.log"
FILE_ERROR = "errors.log"
FILE_JSON = "app.jsonl"  # optionnel (désactivé par défaut)


# =========================
# Utilitaires internes
# =========================
def _project_root_from_backend() -> str:
    """
    backend/logs.py -> parent = racine projet (BASE_DIR).
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_str() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_str(x: Any, max_len: int = 1200) -> str:
    """
    Convertit un objet en string sans exploser les logs.
    """
    try:
        s = str(x)
    except Exception:
        s = "<unprintable>"
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _safe_repr(x: Any, max_len: int = 1200) -> str:
    """
    repr() sécurisé et tronqué.
    """
    try:
        s = repr(x)
    except Exception:
        s = "<unreprable>"
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(key)
    return v if v is not None else default


# =========================
# Contexte global (session)
# =========================
@dataclass(frozen=True)
class LogContext:
    session_id: str
    app_name: str
    base_dir: str
    log_dir: str


_CONTEXT: Optional[LogContext] = None


def get_context() -> LogContext:
    """
    Retourne le contexte logging courant. setup_logging() doit avoir été appelé.
    """
    global _CONTEXT
    if _CONTEXT is None:
        # fallback minimal si importé avant setup_logging()
        base_dir = _project_root_from_backend()
        log_dir = os.path.join(base_dir, "output", "logs")
        return LogContext(session_id="no-session", app_name=DEFAULT_APP_NAME, base_dir=base_dir, log_dir=log_dir)
    return _CONTEXT


# =========================
# Formatters
# =========================
class RichFormatter(logging.Formatter):
    """
    Formatter lisible, riche et très utile pour debug.
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_context()
        record.session_id = getattr(record, "session_id", ctx.session_id)

        # record.pathname peut être long ; record.filename est plus lisible
        timestamp = _dt.datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        thread = record.threadName
        proc = record.process
        loc = f"{record.filename}:{record.lineno} ({record.funcName})"
        base = f"{timestamp} | {record.levelname:<8} | pid={proc} | th={thread} | sid={record.session_id} | {loc} | {record.getMessage()}"

        if record.exc_info:
            # traceback complet
            tb = "".join(traceback.format_exception(*record.exc_info))
            return f"{base}\n{tb}"
        return base


class JsonLinesFormatter(logging.Formatter):
    """
    Formatter JSONL (une ligne JSON par événement).
    Pratique pour parsing / ingestion (ELK, Loki, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_context()
        payload = {
            "ts": _dt.datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "pid": record.process,
            "thread": record.threadName,
            "file": record.filename,
            "line": record.lineno,
            "func": record.funcName,
            "session_id": getattr(record, "session_id", ctx.session_id),
        }
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


# =========================
# Handlers
# =========================
def _make_rotating_file_handler(path: str, level: int, formatter: logging.Formatter) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=DEFAULT_MAX_BYTES,
        backupCount=DEFAULT_BACKUP_COUNT,
        encoding=DEFAULT_ENCODING,
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def _make_console_handler(level: int, formatter: logging.Formatter) -> logging.Handler:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


# =========================
# API publique (setup / get_logger)
# =========================
def setup_logging(
    base_dir: Optional[str] = None,
    app_name: str = DEFAULT_APP_NAME,
    level: str = DEFAULT_LEVEL,
    log_dir: Optional[str] = None,
    enable_jsonl: bool = False,
    quiet_console: bool = False,
) -> LogContext:
    """
    Configure la journalisation globale de l'application.

    Paramètres :
    - base_dir : racine projet (BASE_DIR). Par défaut : parent de backend/
    - app_name : nom de l'app (affecte le dossier de logs)
    - level : "DEBUG" | "INFO" | "WARNING" | ...
    - log_dir : chemin des logs ; par défaut : <base_dir>/output/logs/<app_name>/
    - enable_jsonl : active app.jsonl en plus de app.log
    - quiet_console : si True, console au niveau INFO (même si fichiers en DEBUG)
    """
    global _CONTEXT

    if base_dir is None:
        base_dir = _project_root_from_backend()

    if log_dir is None:
        log_dir = os.path.join(base_dir, "output", "logs", app_name)

    _ensure_dir(log_dir)

    session_id = uuid.uuid4().hex[:12]
    _CONTEXT = LogContext(session_id=session_id, app_name=app_name, base_dir=base_dir, log_dir=log_dir)

    # Niveau global
    level_upper = (level or DEFAULT_LEVEL).upper().strip()
    lvl = getattr(logging, level_upper, logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(lvl)

    # IMPORTANT : éviter les handlers dupliqués si setup_logging est appelé plusieurs fois
    _clear_handlers(root)

    rich_fmt = RichFormatter()
    json_fmt = JsonLinesFormatter()

    # Fichiers
    main_path = os.path.join(log_dir, FILE_MAIN)
    err_path = os.path.join(log_dir, FILE_ERROR)

    root.addHandler(_make_rotating_file_handler(main_path, lvl, rich_fmt))

    # Fichier erreurs : capture WARNING+ ou ERROR+ ? -> ERROR recommandé pour être clair
    err_level = logging.ERROR
    root.addHandler(_make_rotating_file_handler(err_path, err_level, rich_fmt))

    # JSONL optionnel
    if enable_jsonl:
        json_path = os.path.join(log_dir, FILE_JSON)
        root.addHandler(_make_rotating_file_handler(json_path, lvl, json_fmt))

    # Console
    console_level = logging.INFO if quiet_console else lvl
    root.addHandler(_make_console_handler(console_level, rich_fmt))

    # Warnings -> logging
    _install_warning_capture()

    # Exceptions non gérées -> logging
    _install_excepthooks()

    # Petit banner démarrage
    log = get_logger(__name__)
    log.info("Logging initialisé | app=%s | level=%s | log_dir=%s", app_name, level_upper, log_dir)

    return _CONTEXT


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger prêt à l'emploi.
    Ajoute automatiquement session_id via LoggerAdapter.
    """
    base = logging.getLogger(name)
    ctx = get_context()
    return logging.LoggerAdapter(base, extra={"session_id": ctx.session_id})  # type: ignore[arg-type]


def get_log_paths() -> Dict[str, str]:
    """
    Retourne les chemins utiles des fichiers de logs.
    """
    ctx = get_context()
    return {
        "log_dir": ctx.log_dir,
        "main_log": os.path.join(ctx.log_dir, FILE_MAIN),
        "error_log": os.path.join(ctx.log_dir, FILE_ERROR),
        "jsonl_log": os.path.join(ctx.log_dir, FILE_JSON),
    }


def _clear_handlers(logger: logging.Logger) -> None:
    for h in list(logger.handlers):
        try:
            logger.removeHandler(h)
            h.close()
        except Exception:
            pass


# =========================
# Capture warnings / exceptions
# =========================
def _install_warning_capture() -> None:
    # redirige warnings.warn(...) vers logging
    logging.captureWarnings(True)
    wlog = logging.getLogger("py.warnings")
    # assure un niveau raisonnable
    wlog.setLevel(logging.WARNING)


def _install_excepthooks() -> None:
    """
    Capture :
    - exceptions non catchées du thread principal (sys.excepthook)
    - exceptions non catchées des threads (threading.excepthook, py3.8+)
    """
    log = get_logger("UNHANDLED")

    def _sys_hook(exctype, value, tb):
        try:
            log.critical("Exception non gérée (main thread)", exc_info=(exctype, value, tb))
        except Exception:
            # dernier recours
            print("Exception non gérée (main thread) :", exctype, value)
            traceback.print_tb(tb)

    sys.excepthook = _sys_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            try:
                log.critical(
                    "Exception non gérée (thread=%s)",
                    getattr(args, "thread", None).name if getattr(args, "thread", None) else "unknown",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            except Exception:
                print("Exception non gérée (thread)")
        threading.excepthook = _thread_hook  # type: ignore[attr-defined]


# =========================
# Informations système (utile en début de run)
# =========================
def log_system_info(logger: Optional[logging.Logger] = None) -> None:
    """
    Log un snapshot système utile pour debug environnement / chemins / versions.
    """
    log = logger or get_logger("SYSTEM")

    ctx = get_context()
    log.info("=== SYSTEM INFO ===")
    log.info("Timestamp        : %s", _now_str())
    log.info("App              : %s", ctx.app_name)
    log.info("Session          : %s", ctx.session_id)
    log.info("Base dir         : %s", ctx.base_dir)
    log.info("Log dir          : %s", ctx.log_dir)
    log.info("CWD              : %s", os.getcwd())
    log.info("Python           : %s", sys.version.replace("\n", " "))
    log.info("Executable       : %s", sys.executable)
    log.info("Platform         : %s", platform.platform())
    log.info("Machine          : %s", platform.machine())
    log.info("Processor        : %s", platform.processor())
    log.info("PID              : %s", os.getpid())
    log.info("Args             : %s", _safe_repr(sys.argv))
    log.info("PATH sys.path[0] : %s", sys.path[0] if sys.path else "—")

    # Variables utiles si tu en ajoutes dans le futur
    for k in ["KIVY_NO_ARGS", "KIVY_GL_BACKEND", "PYTHONPATH", "VIRTUAL_ENV"]:
        v = _env(k)
        if v:
            log.info("Env %-12s : %s", k, _safe_str(v, 500))

    log.info("===================")


# =========================
# Outils de debug (timer / dump / trace)
# =========================
@contextlib.contextmanager
def log_time(label: str, logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """
    Context manager : mesure le temps d'un bloc.
    """
    log = logger or get_logger("TIMER")
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = (time.perf_counter() - t0) * 1000.0
        log.log(level, "%s | %.2f ms", label, dt)


def dump_dict(
    d: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    title: str = "DUMP",
    max_items: int = 200,
    max_value_len: int = 800,
    level: int = logging.DEBUG,
) -> None:
    """
    Dump lisible d'un dict (trié), sans exploser les logs.
    """
    log = logger or get_logger("DUMP")
    log.log(level, "=== %s (len=%s) ===", title, len(d))

    for i, k in enumerate(sorted(d.keys(), key=lambda x: str(x))):
        if i >= max_items:
            log.log(level, "... (%s éléments restants tronqués)", len(d) - max_items)
            break
        v = d[k]
        log.log(level, " - %s : %s", k, _safe_str(v, max_value_len))

    log.log(level, "=== /%s ===", title)


def trace_calls(
    logger: Optional[logging.Logger] = None,
    level: int = logging.DEBUG,
    show_args: bool = True,
    show_return: bool = False,
    max_len: int = 400,
) -> Callable:
    """
    Décorateur : log entrée/sortie fonction + durée.
    Très utile sur une fonction qui bugge.

    Exemple :
        @trace_calls(get_logger(__name__), show_return=True)
        def foo(a, b): ...
    """
    log = logger or get_logger("TRACE")

    def deco(fn: Callable):
        def wrapper(*args, **kwargs):
            name = f"{fn.__module__}.{fn.__qualname__}"
            if show_args:
                log.log(level, "-> %s args=%s kwargs=%s", name, _safe_repr(args, max_len), _safe_repr(kwargs, max_len))
            else:
                log.log(level, "-> %s", name)

            t0 = time.perf_counter()
            try:
                out = fn(*args, **kwargs)
            except Exception:
                log.exception("!! %s a levé une exception", name)
                raise
            finally:
                dt = (time.perf_counter() - t0) * 1000.0
                log.log(level, "<- %s (%.2f ms)", name, dt)

            if show_return:
                log.log(level, "<- %s return=%s", name, _safe_repr(out, max_len))
            return out

        return wrapper

    return deco


def log_exception(
    message: str,
    logger: Optional[logging.Logger] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Helper : log.exception avec message + extra (dump court).
    """
    log = logger or get_logger("EXC")
    if extra:
        log.error("Contexte : %s", _safe_repr(extra, 1200))
    log.exception(message)


# =========================
# Bridge Kivy (optionnel)
# =========================
def install_kivy_bridge(logger: Optional[logging.Logger] = None) -> None:
    """
    Optionnel : tente de brancher le logger Kivy vers python logging.
    À appeler après setup_logging() si tu veux voir les logs kivy dans tes fichiers.

    Remarque : selon version/config Kivy, ce bridge peut être inutile.
    """
    log = logger or get_logger("KIVY")

    try:
        from kivy.logger import Logger as KivyLogger  # type: ignore
        # KivyLogger est basé sur logging mais peut avoir ses propres handlers.
        # Ici on s'assure juste que KivyLogger propage au root python logging.
        KivyLogger.propagate = True
        log.info("Bridge Kivy installé (propagate=True).")
    except Exception as e:
        log.warning("Bridge Kivy non installé : %s", e)
