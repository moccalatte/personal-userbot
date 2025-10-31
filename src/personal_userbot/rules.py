"""Keyword rule loading, evaluation, and persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    """Represents a keyword match rule."""

    label: str
    include_all: Sequence[str]
    include_any: Sequence[str]
    exclude: Sequence[str]
    chat_ids: Optional[Set[int]]

    def applies_to_chat(self, chat_id: int | None) -> bool:
        if chat_id is None or self.chat_ids is None:
            return True
        return chat_id in self.chat_ids


class RuleSet:
    """Collection of rules with evaluation helpers."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        self._rules: List[Rule] = list(rules)
        self._rebuild_chat_cache()

    @property
    def rules(self) -> Sequence[Rule]:
        return self._rules

    @property
    def chat_ids(self) -> Optional[Set[int]]:
        return self._chat_ids or None

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)
        if rule.chat_ids:
            self._chat_ids.update(rule.chat_ids)

    def replace(self, rules: Iterable[Rule]) -> None:
        self._rules = list(rules)
        self._rebuild_chat_cache()

    def _rebuild_chat_cache(self) -> None:
        chat_ids: Set[int] = set()
        for rule in self._rules:
            if rule.chat_ids:
                chat_ids.update(rule.chat_ids)
        self._chat_ids = chat_ids

    def match(self, chat_id: int | None, text: str) -> List[Rule]:
        """Return rules that match the provided message text."""
        normalized = (text or "").casefold()
        matches: List[Rule] = []
        for rule in self._rules:
            if not rule.applies_to_chat(chat_id):
                continue

            if rule.include_all and not all(
                keyword.casefold() in normalized for keyword in rule.include_all
            ):
                continue

            if rule.include_any and not any(
                keyword.casefold() in normalized for keyword in rule.include_any
            ):
                continue

            if rule.exclude and any(
                keyword.casefold() in normalized for keyword in rule.exclude
            ):
                continue

            matches.append(rule)
        return matches


def _ensure_list(value, *, field: str, label: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"Field '{field}' for rule '{label}' must be a string or list.")


def _parse_chat_ids(value, label: str) -> Optional[Set[int]]:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(
            f"Field 'chats' for rule '{label}' must be a list of integers."
        )
    chat_ids: Set[int] = set()
    for item in value:
        try:
            chat_ids.add(int(item))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid chat id '{item}' for rule '{label}'."
            ) from exc
    return chat_ids or None


def load_rules(path: Path) -> RuleSet:
    """Load rules definition from a JSON file. Returns empty set if missing."""

    logger.info("Loading rules from %s", path)
    if not path.exists():
        logger.info(
            "Rules file '%s' tidak ditemukan. Memulai dengan rule set kosong.",
            path,
        )
        return RuleSet([])

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Tidak bisa membaca file rules '{path}': {exc}") from exc

    if not raw_text.strip():
        logger.info("Rules file '%s' kosong. Memulai dengan rule set kosong.", path)
        return RuleSet([])

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Rules file '{path}' tidak valid. Periksa format JSON: {exc}"
        ) from exc

    if isinstance(data, dict):
        raw_rules = data.get("rules") or []
    elif isinstance(data, list):
        raw_rules = data
    else:
        raise RuntimeError(
            f"Rules file '{path}' harus berupa objek dengan field 'rules' atau list."
        )

    if not isinstance(raw_rules, list):
        raise RuntimeError(f"Field 'rules' pada '{path}' harus berupa list.")

    rules: List[Rule] = []
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise RuntimeError("Setiap rule harus berbentuk objek dengan key-value.")
        label = str(raw.get("label") or raw.get("name") or "").strip()
        if not label:
            raise RuntimeError("Setiap rule wajib memiliki field 'label'.")

        include_all = _ensure_list(
            raw.get("include_all") or raw.get("include"), field="include_all", label=label
        )
        include_any = _ensure_list(
            raw.get("include_any"), field="include_any", label=label
        )
        exclude = _ensure_list(
            raw.get("exclude"), field="exclude", label=label
        )
        chat_ids = _parse_chat_ids(raw.get("chats"), label)

        if not include_all and not include_any:
            raise RuntimeError(
                f"Rule '{label}' perlu setidaknya satu keyword via "
                "'include_all' atau 'include_any'."
            )

        rules.append(
            Rule(
                label=label,
                include_all=include_all,
                include_any=include_any,
                exclude=exclude,
                chat_ids=chat_ids,
            )
        )

    logger.info("Loaded %d rules", len(rules))
    return RuleSet(rules)


def save_rules(path: Path, rules: Sequence[Rule]) -> None:
    """Persist rules to disk as JSON."""

    serialized = []
    for rule in rules:
        entry = {
            "label": rule.label,
            "include_all": list(rule.include_all),
            "include_any": list(rule.include_any),
            "exclude": list(rule.exclude),
        }
        if rule.chat_ids:
            entry["chats"] = sorted(rule.chat_ids)
        serialized.append(entry)

    payload = {"rules": serialized}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved %d rules to %s", len(serialized), path)


class RuleRepository:
    """Helper to load, cache, and persist rules."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._ruleset = load_rules(path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def ruleset(self) -> RuleSet:
        return self._ruleset

    def add_rule(self, rule: Rule) -> None:
        self._ruleset.add_rule(rule)
        save_rules(self._path, self._ruleset.rules)

    def replace(self, rules: Iterable[Rule]) -> None:
        self._ruleset.replace(rules)
        save_rules(self._path, self._ruleset.rules)
