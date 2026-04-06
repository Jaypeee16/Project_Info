from __future__ import annotations

import json
import shutil
import re
import sys
import uuid
import os
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import simpledialog, messagebox

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover - import guard for runtime dependency
    raise SystemExit(
        "customtkinter is required. Install dependencies with: pip install -r requirements.txt"
    ) from exc


PLAYFAIR_KEY = "SECRET"
XOR_KEY = "SUPERSECRETKEY"
APP_VERSION = "1.1.0"

# ============= Passphrase-based Key Derivation =============
PBKDF2_ITERATIONS = 100000
SALT_SIZE = 32
VERIFICATION_TOKEN = "SECURE_JOURNAL_VERIFICATION"
GLOBAL_PLAYFAIR_KEY = None
GLOBAL_XOR_KEY = None
GLOBAL_PASSPHRASE = None


def _app_data_file() -> Path:
    # When frozen (PyInstaller), keep data beside the executable.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name("journal_data.json")
    return Path(__file__).resolve().with_name("journal_data.json")


DATA_FILE = _app_data_file()
PLAYFAIR_ALPHABET = "ABCDEFGHIKLMNOPQRSTUVWXYZ"
PLAYFAIR_FILLERS = ("X", "Q")

APP_BG = "#0b1118"
PANEL_BG = "#121923"
PANEL_ALT = "#18212c"
CARD_BG = "#1b2631"
CARD_SELECTED = "#223d41"
CARD_BORDER = "#2b3a46"
ACCENT = "#5a8f88"
ACCENT_HOVER = "#6aa79f"
DELETE = "#8a4f4f"
DELETE_HOVER = "#a86464"
TEXT = "#e8edf2"
TEXT_MUTED = "#a4afba"
TEXT_DIM = "#74808b"


@dataclass
class JournalRecord:
    id: str
    title: str
    tags: str
    mood: str
    content: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, raw: Any) -> JournalRecord | None:
        if not isinstance(raw, dict):
            return None
        return cls(
            id=str(raw.get("id", "")),
            title=str(raw.get("title", "")),
            tags=str(raw.get("tags", "")),
            mood=str(raw.get("mood", "")),
            content=str(raw.get("content", "")),
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "tags": self.tags,
            "mood": self.mood,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============= Key Derivation Functions =============
def generate_salt() -> str:
    """Generate a cryptographic salt for PBKDF2."""
    return os.urandom(SALT_SIZE).hex()


def derive_keys_from_passphrase(passphrase: str, salt: str) -> tuple[str, str, str]:
    """
    Derive two encryption keys from a passphrase using PBKDF2.
    
    Returns:
        (playfair_key, xor_key, verification_token)
    """
    if not passphrase or not salt:
        raise ValueError("Passphrase and salt cannot be empty")
    
    # Derive a master key from passphrase
    salt_bytes = bytes.fromhex(salt)
    master_key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS
    )
    
    # Derive two separate keys from master key
    playfair_key = hashlib.sha256(master_key + b"playfair").hexdigest()[:26]
    xor_key = hashlib.sha256(master_key + b"xor_cipher").hexdigest()[:30]
    
    # Generate verification token
    verification = hmac.new(master_key, VERIFICATION_TOKEN.encode(), hashlib.sha256).hexdigest()
    
    return playfair_key, xor_key, verification


def verify_passphrase(passphrase: str, salt: str, stored_verification: str) -> bool:
    """Verify that the passphrase matches the stored verification token."""
    try:
        _, _, verification = derive_keys_from_passphrase(passphrase, salt)
        return hmac.compare_digest(verification, stored_verification)
    except (ValueError, TypeError):
        return False


def set_global_keys(passphrase: str, salt: str) -> None:
    """Set global encryption keys derived from passphrase."""
    global GLOBAL_PLAYFAIR_KEY, GLOBAL_XOR_KEY, GLOBAL_PASSPHRASE
    playfair_key, xor_key, _ = derive_keys_from_passphrase(passphrase, salt)
    GLOBAL_PLAYFAIR_KEY = playfair_key
    GLOBAL_XOR_KEY = xor_key
    GLOBAL_PASSPHRASE = passphrase


def get_playfair_key() -> str:
    """Get the current Playfair key (derived or fallback)."""
    return GLOBAL_PLAYFAIR_KEY if GLOBAL_PLAYFAIR_KEY else PLAYFAIR_KEY


def get_xor_key() -> str:
    """Get the current XOR key (derived or fallback)."""
    return GLOBAL_XOR_KEY if GLOBAL_XOR_KEY else XOR_KEY


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _format_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %Y")
    except ValueError:
        return value


def _sort_records(records: list[JournalRecord]) -> list[JournalRecord]:
    def sort_key(record: JournalRecord) -> datetime:
        for value in (record.updated_at, record.created_at):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                continue
        return datetime.min

    return sorted(records, key=sort_key, reverse=True)


def _build_playfair_square(key: str) -> tuple[list[list[str]], dict[str, tuple[int, int]]]:
    seen: set[str] = set()
    sequence: list[str] = []
    for character in key.upper():
        if not character.isalpha():
            continue
        character = "I" if character == "J" else character
        if character not in seen:
            seen.add(character)
            sequence.append(character)
    for character in PLAYFAIR_ALPHABET:
        if character not in seen:
            sequence.append(character)
    square = [sequence[index : index + 5] for index in range(0, 25, 5)]
    positions = {character: (row, column) for row, row_values in enumerate(square) for column, character in enumerate(row_values)}
    return square, positions


def _prepare_playfair_segment(segment: str) -> list[str]:
    letters = ["I" if character.upper() == "J" else character.upper() for character in segment if character.isalpha()]
    if not letters:
        return []
    pairs: list[str] = []
    index = 0
    while index < len(letters):
        first = letters[index]
        if index + 1 >= len(letters):
            filler = "Q" if first == "X" else "X"
            pairs.append(first + filler)
            index += 1
            continue
        second = letters[index + 1]
        if first == second:
            filler = "Q" if first == "X" else "X"
            pairs.append(first + filler)
            index += 1
        else:
            pairs.append(first + second)
            index += 2
    return pairs


def _transform_playfair_pair(pair: str, square: list[list[str]], positions: dict[str, tuple[int, int]], encrypt: bool) -> str:
    first, second = pair
    first_row, first_column = positions[first]
    second_row, second_column = positions[second]
    if first_row == second_row:
        offset = 1 if encrypt else -1
        return square[first_row][(first_column + offset) % 5] + square[second_row][(second_column + offset) % 5]
    if first_column == second_column:
        offset = 1 if encrypt else -1
        return square[(first_row + offset) % 5][first_column] + square[(second_row + offset) % 5][second_column]
    return square[first_row][second_column] + square[second_row][first_column]


def _remove_playfair_padding(text: str) -> str:
    if not text:
        return text
    cleaned: list[str] = []
    index = 0
    while index < len(text):
        if index + 2 < len(text) and text[index] == text[index + 2] and text[index + 1] in PLAYFAIR_FILLERS:
            cleaned.append(text[index])
            index += 2
        else:
            cleaned.append(text[index])
            index += 1
    if cleaned and cleaned[-1] in PLAYFAIR_FILLERS:
        cleaned.pop()
    return "".join(cleaned)


def _transform_playfair_text(text: str, encrypt: bool) -> str:
    if not text:
        return ""
    key = get_playfair_key()
    square, positions = _build_playfair_square(key)
    output: list[str] = []
    for segment in re.findall(r"[A-Za-z]+|[^A-Za-z]+", text):
        if not segment.isalpha():
            output.append(segment)
            continue
        if encrypt:
            pairs = _prepare_playfair_segment(segment)
            encoded = "".join(_transform_playfair_pair(pair, square, positions, True) for pair in pairs)
            output.append(encoded)
        else:
            letters = ["I" if character.upper() == "J" else character.upper() for character in segment if character.isalpha()]
            if len(letters) % 2 != 0:
                letters.append("X")
            decoded = "".join(
                _transform_playfair_pair("".join(letters[index : index + 2]), square, positions, False)
                for index in range(0, len(letters), 2)
            )
            output.append(_remove_playfair_padding(decoded))
    return "".join(output)


def playfair_encrypt_text(text: str) -> str:
    return _transform_playfair_text(text, True)


def playfair_decrypt_text(text: str) -> str:
    return _transform_playfair_text(text, False)


def _xor_bytes(payload: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(payload))


def xor_encrypt_hex(text: str) -> str:
    if not text:
        return ""
    key = get_xor_key()
    encrypted = _xor_bytes(text.encode("utf-8"), key.encode("utf-8"))
    return encrypted.hex()


def xor_decrypt_hex(hex_text: str) -> str:
    if not hex_text:
        return ""
    try:
        encrypted = bytes.fromhex(hex_text)
    except ValueError:
        return ""
    key = get_xor_key()
    decrypted = _xor_bytes(encrypted, key.encode("utf-8"))
    return decrypted.decode("utf-8", errors="replace")


def encrypt_record_fields(title: str, tags: str, mood: str, content: str, *, record_id: str | None = None, created_at: str | None = None) -> JournalRecord:
    now = _now_iso()
    return JournalRecord(
        id=record_id or uuid.uuid4().hex,
        title=playfair_encrypt_text(title),
        tags=playfair_encrypt_text(tags),
        mood=playfair_encrypt_text(mood),
        content=xor_encrypt_hex(content),
        created_at=created_at or now,
        updated_at=now,
    )


def decrypt_record_fields(record: JournalRecord) -> dict[str, str]:
    return {
        "title": playfair_decrypt_text(record.title),
        "tags": playfair_decrypt_text(record.tags),
        "mood": playfair_decrypt_text(record.mood),
        "content": xor_decrypt_hex(record.content),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bak")


def load_records(path: Path = DATA_FILE) -> list[JournalRecord]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, dict):
        raw = raw.get("entries", [])
    if not isinstance(raw, list):
        return []
    records = [record for item in raw if (record := JournalRecord.from_dict(item)) is not None]
    return _sort_records(records)


def load_records_detailed(path: Path = DATA_FILE) -> tuple[list[JournalRecord], str | None, str | None, str | None]:
    """Load records with metadata. Returns (records, error_code, salt, verification)."""
    if not path.exists():
        return [], None, None, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], "json_decode_error", None, None
    except OSError:
        return [], "read_error", None, None

    salt = None
    verification = None
    
    # Handle both old format (list) and new format (dict with metadata)
    if isinstance(raw, dict):
        salt = raw.get("salt")
        verification = raw.get("verification")
        raw = raw.get("entries", [])
    
    if not isinstance(raw, list):
        return [], "invalid_shape", None, None

    records = [record for item in raw if (record := JournalRecord.from_dict(item)) is not None]
    return _sort_records(records), None, salt, verification


def save_records(records: list[JournalRecord], path: Path = DATA_FILE, salt: str | None = None, verification: str | None = None) -> None:
    """Save records with optional metadata (salt, verification token)."""
    sorted_records = _sort_records(records)
    
    # Create payload with optional metadata
    if salt and verification:
        payload_dict = {
            "version": "1.1",
            "salt": salt,
            "verification": verification,
            "entries": [record.to_dict() for record in sorted_records]
        }
    else:
        # Fallback to list-only format for backward compatibility
        payload_dict = [record.to_dict() for record in sorted_records]
    
    payload = json.dumps(payload_dict, indent=2)
    backup = _backup_path(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    if path.exists():
        shutil.copy2(path, backup)

    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(path)


def restore_from_backup(path: Path = DATA_FILE) -> bool:
    backup = _backup_path(path)
    if not backup.exists():
        return False
    shutil.copy2(backup, path)
    return True


def sample_draft_fields() -> tuple[str, str, str, str]:
    return (
        "Quiet Reset",
        "sample, personal, evening",
        "calm",
        "Today was slower than expected. I spent the afternoon organizing thoughts, clearing my workspace, and making room for a quieter evening. The focus is simple: less noise, more intention."
    )


class JournalApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(f"Secure Journal v{APP_VERSION}")
        self.geometry("1240x800")
        self.minsize(1040, 680)
        self.configure(fg_color=APP_BG)

        self.records: list[JournalRecord] = []
        self.selected_record_id: str | None = None
        self.mode: str = "view"
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.salt: str | None = None
        self.verification: str | None = None

        self._build_layout()
        self._initialize_passphrase_and_records()
        self._refresh_sidebar()
        self._show_blank_state()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0, width=300)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color=PANEL_BG, corner_radius=0)
        sidebar_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        sidebar_header.grid_columnconfigure(0, weight=1)

        sidebar_title = ctk.CTkLabel(
            sidebar_header,
            text="Secure Journal",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT,
        )
        sidebar_title.grid(row=0, column=0, sticky="w")

        sidebar_subtitle = ctk.CTkLabel(
            sidebar_header,
            text="Stored locally, encrypted",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        )
        sidebar_subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.sample_button = ctk.CTkButton(
            self.sidebar,
            text="Load Sample Draft",
            height=34,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#1d2832",
            border_width=1,
            border_color=CARD_BORDER,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._load_sample_draft,
        )
        self.sample_button.grid(row=1, column=0, sticky="ew", padx=18, pady=(6, 8))

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            textvariable=self.search_var,
            placeholder_text="Search titles, tags, mood",
            height=40,
            corner_radius=10,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
            placeholder_text_color=TEXT_DIM,
        )
        self.search_entry.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))

        self.entries_scroll = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color=PANEL_BG,
            corner_radius=0,
            scrollbar_button_color=ACCENT,
            scrollbar_button_hover_color=ACCENT_HOVER,
        )
        self.entries_scroll.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.main_panel = ctk.CTkFrame(self, fg_color=APP_BG, corner_radius=0)
        self.main_panel.grid(row=0, column=1, sticky="nsew")
        self.main_panel.grid_rowconfigure(1, weight=1)
        self.main_panel.grid_columnconfigure(0, weight=1)

        self.content_frame = ctk.CTkFrame(self.main_panel, fg_color=PANEL_BG, corner_radius=18)
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        header_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 14))
        header_container.grid_columnconfigure(0, weight=1)
        header_container.grid_columnconfigure(1, weight=1)

        title_block = ctk.CTkFrame(header_container, fg_color="transparent")
        title_block.grid(row=0, column=0, columnspan=2, sticky="ew")
        title_block.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(title_block, text="Title", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(
            title_block,
            height=40,
            corner_radius=10,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
            placeholder_text="Enter journal title",
        )
        self.title_entry.grid(row=1, column=0, sticky="ew")

        tags_block = ctk.CTkFrame(header_container, fg_color="transparent")
        tags_block.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(14, 0))
        tags_block.grid_columnconfigure(0, weight=1)
        tags_label = ctk.CTkLabel(tags_block, text="Tags", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"))
        tags_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.tags_entry = ctk.CTkEntry(
            tags_block,
            height=40,
            corner_radius=10,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
            placeholder_text="comma-separated tags",
        )
        self.tags_entry.grid(row=1, column=0, sticky="ew")

        mood_block = ctk.CTkFrame(header_container, fg_color="transparent")
        mood_block.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(14, 0))
        mood_block.grid_columnconfigure(0, weight=1)
        mood_label = ctk.CTkLabel(mood_block, text="Mood", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"))
        mood_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.mood_entry = ctk.CTkEntry(
            mood_block,
            height=40,
            corner_radius=10,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
            placeholder_text="how you feel",
        )
        self.mood_entry.grid(row=1, column=0, sticky="ew")

        body_block = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        body_block.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 14))
        body_block.grid_rowconfigure(1, weight=1)
        body_block.grid_columnconfigure(0, weight=1)

        body_label = ctk.CTkLabel(body_block, text="Journal Entry", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"))
        body_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.body_text = ctk.CTkTextbox(
            body_block,
            corner_radius=12,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
            font=ctk.CTkFont(size=13),
            wrap="word",
        )
        self.body_text.grid(row=1, column=0, sticky="nsew")

        actions_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        actions_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        actions_frame.grid_columnconfigure(0, weight=1)

        self.edit_button = ctk.CTkButton(
            actions_frame,
            text="Edit",
            height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#1f2a33",
            border_width=1,
            border_color=ACCENT,
            text_color=ACCENT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._enter_edit_mode,
        )
        self.edit_button.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.primary_button = ctk.CTkButton(
            actions_frame,
            text="New Entry",
            height=40,
            corner_radius=10,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._primary_action,
        )
        self.primary_button.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        self.delete_button = ctk.CTkButton(
            actions_frame,
            text="Delete",
            height=40,
            corner_radius=10,
            fg_color=DELETE,
            hover_color=DELETE_HOVER,
            text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._delete_selected_entry,
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

        footer = ctk.CTkFrame(self.main_panel, fg_color=PANEL_ALT, corner_radius=0, height=54)
        footer.grid(row=1, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)

        footer_title = ctk.CTkLabel(
            footer,
            text="Journal Entries Encrypted & Protected",
            text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        footer_title.grid(row=0, column=0, sticky="w", padx=20, pady=(8, 0))

        footer_legend = ctk.CTkLabel(
            footer,
            text="Keys derived from passphrase   |   Playfair: title, tags, mood   |   XOR: content",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        footer_legend.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            footer,
            text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.status_label.grid(row=0, column=1, rowspan=2, sticky="e", padx=20)

        self._set_form_editable(False)

    def _on_search_change(self, *_args: object) -> None:
        self._refresh_sidebar()

    def _filtered_records(self) -> list[JournalRecord]:
        query = self.search_var.get().strip().lower()
        if not query:
            return list(self.records)
        filtered: list[JournalRecord] = []
        for record in self.records:
            decrypted = decrypt_record_fields(record)
            search_blob = " ".join((decrypted["title"], decrypted["tags"], decrypted["mood"]))
            if query in search_blob.lower():
                filtered.append(record)
        return filtered

    def _refresh_sidebar(self) -> None:
        for child in self.entries_scroll.winfo_children():
            child.destroy()
        filtered = self._filtered_records()
        if not filtered:
            placeholder = ctk.CTkLabel(
                self.entries_scroll,
                text="No journal entries yet.",
                font=ctk.CTkFont(size=13),
                text_color=TEXT_MUTED,
            )
            placeholder.grid(row=0, column=0, sticky="ew", padx=14, pady=16)
            self._update_action_buttons()
            return
        for index, record in enumerate(filtered):
            decrypted = decrypt_record_fields(record)
            self._create_entry_card(record, decrypted["title"], decrypted["created_at"], index)
        self._update_action_buttons()

    def _create_entry_card(self, record: JournalRecord, title: str, created_at: str, row: int) -> None:
        selected = record.id == self.selected_record_id
        card = ctk.CTkFrame(
            self.entries_scroll,
            fg_color=CARD_SELECTED if selected else CARD_BG,
            border_width=1,
            border_color=ACCENT if selected else CARD_BORDER,
            corner_radius=12,
        )
        card.grid(row=row, column=0, sticky="ew", padx=4, pady=5)
        card.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        top_row.grid_columnconfigure(1, weight=1)

        lock_label = ctk.CTkLabel(top_row, text="🔒", text_color=ACCENT if selected else TEXT_MUTED, font=ctk.CTkFont(size=14))
        lock_label.grid(row=0, column=0, sticky="w")

        title_label = ctk.CTkLabel(
            top_row,
            text=title.strip() or "(UNTITLED)",
            text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=196,
        )
        title_label.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        date_label = ctk.CTkLabel(
            card,
            text=_format_date(created_at),
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=10),
            anchor="w",
            justify="left",
        )
        date_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._bind_click(card, lambda _event, entry_id=record.id: self._select_record(entry_id))

    def _bind_click(self, widget: tk.Widget, callback) -> None:
        widget.bind("<Button-1>", callback)
        for child in widget.winfo_children():
            self._bind_click(child, callback)

    def _set_form_editable(self, editable: bool) -> None:
        state = "normal" if editable else "disabled"
        self.title_entry.configure(state=state)
        self.tags_entry.configure(state=state)
        self.mood_entry.configure(state=state)
        self.body_text.configure(state=state)

    def _clear_form(self) -> None:
        for entry in (self.title_entry, self.tags_entry, self.mood_entry):
            entry.configure(state="normal")
            entry.delete(0, tk.END)
        self.body_text.configure(state="normal")
        self.body_text.delete("1.0", tk.END)

    def _fill_form(self, record: JournalRecord) -> None:
        decrypted = decrypt_record_fields(record)
        self.title_entry.configure(state="normal")
        self.tags_entry.configure(state="normal")
        self.mood_entry.configure(state="normal")
        self.body_text.configure(state="normal")

        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, decrypted["title"])
        self.tags_entry.delete(0, tk.END)
        self.tags_entry.insert(0, decrypted["tags"])
        self.mood_entry.delete(0, tk.END)
        self.mood_entry.insert(0, decrypted["mood"])
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert("1.0", decrypted["content"])

    def _show_blank_state(self) -> None:
        self.selected_record_id = None
        self.mode = "view"
        self._clear_form()
        self._set_form_editable(False)
        self._update_action_buttons()
        self._refresh_sidebar()
        self.status_label.configure(text=f"Storage: {DATA_FILE.name}")

    def _initialize_passphrase_and_records(self) -> None:
        """Initialize passphrase and load records."""
        records, error_code, salt, verification = load_records_detailed(DATA_FILE)
        
        # Check if journal already has passphrase protection
        if salt and verification:
            # Existing journal with passphrase - prompt for passphrase
            passphrase = self._prompt_for_passphrase("Enter Passphrase", "Enter your journal passphrase:")
            if passphrase is None:
                messagebox.showwarning("Secure Journal", "No passphrase provided. Starting with empty view.")
                self.records = []
                return
            
            if not verify_passphrase(passphrase, salt, verification):
                messagebox.showerror("Secure Journal", "Incorrect passphrase. Cannot load journal.")
                self.records = []
                return
            
            set_global_keys(passphrase, salt)
            self.salt = salt
            self.verification = verification
            
            if error_code is None:
                self.records = records
                return
        else:
            # New journal or legacy journal - offer setup
            if error_code is None and records:
                # Legacy journal exists with data - offer to protect with passphrase
                setup = messagebox.askyesno(
                    "Secure Journal",
                    "Your journal appears to be using legacy encryption.\n\nWould you like to set up passphrase protection now?",
                )
                if setup:
                    self._setup_passphrase_for_existing_journal(records)
                    return
                else:
                    self.records = records
                    return
            elif error_code is None and not records:
                # New empty journal - offer passphrase setup
                setup = messagebox.askyesno(
                    "Secure Journal",
                    "Set up passphrase protection for your journal?",
                )
                if setup:
                    self._setup_new_journal_with_passphrase()
                    return
                self.records = []
                return
        
        # Handle errors
        if error_code in {"json_decode_error", "invalid_shape"}:
            should_restore = messagebox.askyesno(
                "Secure Journal",
                "Journal data looks corrupted or invalid. Restore from backup if available?",
            )
            if should_restore and restore_from_backup(DATA_FILE):
                restored_records, restored_error, res_salt, res_verification = load_records_detailed(DATA_FILE)
                if restored_error is None:
                    self.records = restored_records
                    self.salt = res_salt
                    self.verification = res_verification
                    if res_salt and res_verification:
                        passphrase = self._prompt_for_passphrase("Restore Passphrase", "Enter your journal passphrase:")
                        if passphrase and verify_passphrase(passphrase, res_salt, res_verification):
                            set_global_keys(passphrase, res_salt)
                    messagebox.showinfo("Secure Journal", "Backup restored successfully.")
                    return
                messagebox.showwarning("Secure Journal", "Backup exists but could not be loaded.")
            else:
                messagebox.showwarning("Secure Journal", "Starting with an empty in-memory journal view.")
        elif error_code == "read_error":
            messagebox.showwarning("Secure Journal", "Could not read journal data. Starting with an empty in-memory journal view.")

        self.records = []
    
    def _prompt_for_passphrase(self, title: str, prompt: str) -> str | None:
        """Show a dialog to prompt for passphrase."""
        dialog = ctk.CTk()
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.configure(fg_color=APP_BG)
        dialog.resizable(False, False)
        
        # Center on screen
        dialog.update_idletasks()
        
        frame = ctk.CTkFrame(dialog, fg_color=PANEL_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        label = ctk.CTkLabel(frame, text=prompt, text_color=TEXT, font=ctk.CTkFont(size=13))
        label.pack(pady=(0, 10))
        
        entry = ctk.CTkEntry(
            frame,
            show="•",
            height=40,
            fg_color=PANEL_ALT,
            border_color=CARD_BORDER,
            text_color=TEXT,
        )
        entry.pack(fill="x", pady=(0, 15))
        entry.focus_set()
        
        result = {"value": None}
        
        def on_ok() -> None:
            result["value"] = entry.get()
            dialog.destroy()
        
        def on_cancel() -> None:
            dialog.destroy()
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        ok_button = ctk.CTkButton(
            button_frame,
            text="OK",
            height=36,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=TEXT,
            command=on_ok,
        )
        ok_button.pack(side="left", padx=(0, 10), fill="x", expand=True)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            height=36,
            fg_color="transparent",
            hover_color="#1f2a33",
            border_width=1,
            border_color=CARD_BORDER,
            text_color=TEXT,
            command=on_cancel,
        )
        cancel_button.pack(side="left", fill="x", expand=True)
        
        dialog.wait_window()
        return result["value"] if result["value"] else None
    
    def _setup_new_journal_with_passphrase(self) -> None:
        """Set up passphrase for a new journal."""
        passphrase = self._prompt_for_passphrase("Set Passphrase", "Create a passphrase (min 6 chars):")
        if not passphrase:
            messagebox.showwarning("Secure Journal", "Passphrase setup cancelled. Using hardcoded keys.")
            return
        
        if len(passphrase) < 6:
            messagebox.showwarning("Secure Journal", "Passphrase too short. Minimum 6 characters. Using hardcoded keys.")
            return
        
        # Generate salt and set keys
        self.salt = generate_salt()
        _, _, verification = derive_keys_from_passphrase(passphrase, self.salt)
        self.verification = verification
        set_global_keys(passphrase, self.salt)
        
        self.records = []
        messagebox.showinfo("Secure Journal", "Passphrase protection enabled successfully!")
    
    def _setup_passphrase_for_existing_journal(self, records: list[JournalRecord]) -> None:
        """Upgrade existing journal to use passphrase protection."""
        passphrase = self._prompt_for_passphrase("Set Passphrase", "Create a passphrase (min 6 chars):")
        if not passphrase:
            messagebox.showwarning("Secure Journal", "Setup cancelled.")
            self.records = records
            return
        
        if len(passphrase) < 6:
            messagebox.showwarning("Secure Journal", "Passphrase too short. Minimum 6 characters.")
            self.records = records
            return
        
        # Generate salt and re-encrypt all records
        self.salt = generate_salt()
        _, _, verification = derive_keys_from_passphrase(passphrase, self.salt)
        self.verification = verification
        set_global_keys(passphrase, self.salt)
        
        # Re-encrypt all records with new keys
        re_encrypted = []
        for record in records:
            # Decrypt with old keys
            decrypted = decrypt_record_fields(record)
            # Re-encrypt with new keys
            new_record = encrypt_record_fields(
                decrypted["title"],
                decrypted["tags"],
                decrypted["mood"],
                decrypted["content"],
                record_id=record.id,
                created_at=record.created_at
            )
            re_encrypted.append(new_record)
        
        self.records = re_encrypted
        
        try:
            save_records(self.records, DATA_FILE, self.salt, self.verification)
            messagebox.showinfo("Secure Journal", "Journal upgraded to passphrase protection!")
        except OSError as exc:
            messagebox.showerror("Secure Journal", f"Could not save protected journal:\n{exc}")
    
    def _initialize_records_with_recovery(self) -> None:
        """Legacy method - kept for backward compatibility."""
        records, error_code, salt, verification = load_records_detailed(DATA_FILE)
        if error_code is None:
            self.records = records
            self.salt = salt
            self.verification = verification
            return

        if error_code in {"json_decode_error", "invalid_shape"}:
            should_restore = messagebox.askyesno(
                "Secure Journal",
                "Journal data looks corrupted or invalid. Restore from backup if available?",
            )
            if should_restore and restore_from_backup(DATA_FILE):
                restored_records, restored_error, res_salt, res_verification = load_records_detailed(DATA_FILE)
                if restored_error is None:
                    self.records = restored_records
                    self.salt = res_salt
                    self.verification = res_verification
                    messagebox.showinfo("Secure Journal", "Backup restored successfully.")
                    return
                messagebox.showwarning("Secure Journal", "Backup exists but could not be loaded.")
            else:
                messagebox.showwarning("Secure Journal", "Starting with an empty in-memory journal view.")
        elif error_code == "read_error":
            messagebox.showwarning("Secure Journal", "Could not read journal data. Starting with an empty in-memory journal view.")

        self.records = []

    def _load_sample_draft(self) -> None:
        title, tags, mood, content = sample_draft_fields()
        self.selected_record_id = None
        self.mode = "create"
        self._clear_form()
        self._set_form_editable(True)
        self.title_entry.insert(0, title)
        self.tags_entry.insert(0, tags)
        self.mood_entry.insert(0, mood)
        self.body_text.insert("1.0", content)
        self._update_action_buttons()
        self.status_label.configure(text="Sample draft loaded. Save it when ready.")

    def _show_record(self, record: JournalRecord) -> None:
        self.selected_record_id = record.id
        self.mode = "view"
        self._fill_form(record)
        self._set_form_editable(False)
        self._update_action_buttons()
        self._refresh_sidebar()
        self.status_label.configure(text=f"Viewing entry updated {_format_date(record.updated_at)}")

    def _select_record(self, entry_id: str) -> None:
        record = self._get_record(entry_id)
        if record is None:
            return
        self._show_record(record)

    def _get_record(self, entry_id: str | None) -> JournalRecord | None:
        if entry_id is None:
            return None
        for record in self.records:
            if record.id == entry_id:
                return record
        return None

    def _update_action_buttons(self) -> None:
        has_selection = self._get_record(self.selected_record_id) is not None
        if self.mode == "view":
            self.primary_button.configure(text="New Entry")
            self.edit_button.configure(state="normal" if has_selection else "disabled")
            self.delete_button.configure(state="normal" if has_selection else "disabled")
        elif self.mode == "create":
            self.primary_button.configure(text="Save")
            self.edit_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
        elif self.mode == "edit":
            self.primary_button.configure(text="Save")
            self.edit_button.configure(state="disabled")
            self.delete_button.configure(state="normal" if has_selection else "disabled")

    def _enter_edit_mode(self) -> None:
        if self.selected_record_id is None:
            return
        if self._get_record(self.selected_record_id) is None:
            return
        self.mode = "edit"
        self._set_form_editable(True)
        self._update_action_buttons()
        self.status_label.configure(text="Editing selected entry")

    def _start_new_entry(self) -> None:
        self.selected_record_id = None
        self.mode = "create"
        self._clear_form()
        self._set_form_editable(True)
        self._update_action_buttons()
        self.title_entry.focus_set()
        self.status_label.configure(text="Creating a new entry")

    def _primary_action(self) -> None:
        if self.mode == "view":
            self._start_new_entry()
            return
        self._save_current_entry()

    def _collect_form_values(self) -> tuple[str, str, str, str]:
        return (
            self.title_entry.get().strip(),
            self.tags_entry.get().strip(),
            self.mood_entry.get().strip(),
            self.body_text.get("1.0", tk.END).rstrip("\n"),
        )

    def _save_current_entry(self) -> None:
        title, tags, mood, content = self._collect_form_values()
        if not any((title, tags, mood, content)):
            messagebox.showwarning("Secure Journal", "Please enter some text before saving.")
            return

        existing = self._get_record(self.selected_record_id) if self.selected_record_id else None
        if existing is None:
            created_at = _now_iso()
            record = encrypt_record_fields(title, tags, mood, content, created_at=created_at)
        else:
            record = encrypt_record_fields(title, tags, mood, content, record_id=existing.id, created_at=existing.created_at)
        self.records = [item for item in self.records if item.id != record.id]
        self.records.append(record)
        self.records = _sort_records(self.records)
        try:
            save_records(self.records, DATA_FILE, self.salt, self.verification)
        except OSError as exc:
            messagebox.showerror("Secure Journal", f"Could not save journal data:\n{exc}")
            return

        self.selected_record_id = record.id
        self.mode = "view"
        self._fill_form(record)
        self._set_form_editable(False)
        self._refresh_sidebar()
        self._update_action_buttons()
        self.status_label.configure(text="Entry saved and encrypted")

    def _delete_selected_entry(self) -> None:
        if self.selected_record_id is None:
            return
        record = self._get_record(self.selected_record_id)
        if record is None:
            return
        if not messagebox.askyesno("Secure Journal", "Delete the selected journal entry?"):
            return

        self.records = [item for item in self.records if item.id != record.id]
        try:
            save_records(self.records, DATA_FILE, self.salt, self.verification)
        except OSError as exc:
            messagebox.showerror("Secure Journal", f"Could not delete journal data:\n{exc}")
            return

        visible_records = self._filtered_records()
        next_record = visible_records[0] if visible_records else (self.records[0] if self.records else None)
        if next_record is None:
            self._show_blank_state()
            self.status_label.configure(text="Entry deleted")
            return
        self._show_record(next_record)
        self.status_label.configure(text="Entry deleted")


def main() -> None:
    app = JournalApp()
    app.mainloop()


if __name__ == "__main__":
    main()