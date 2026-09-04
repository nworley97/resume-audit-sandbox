"""Compatibility helpers for structured resume data produced by AI extractors."""

from __future__ import annotations

import json
import re
from collections import deque


_CONTAINER_KEYS = {
    "candidate", "data", "output", "parsed_resume", "result", "resume",
    "resume_data", "structured_resume",
}

_CONTENT_KEYS = {
    "academic_background", "academic_history", "basics", "career_summary",
    "certificates", "certifications", "competencies", "core_skills", "education",
    "employment", "employment_history", "experience", "objective", "personal_info",
    "personal_information", "professional_experience", "professional_summary", "profile",
    "projects", "skills", "summary", "technical_skills", "work", "work_experience",
    "work_history",
}


def _normalized_key(value) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _mapping(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.lstrip().startswith("{"):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _normalize_collection(value, *, containers, item_keys, label_key):
    """Normalize list sections that AI models commonly wrap or key by label."""
    if value in (None, "", [], {}):
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [_normalize_item(item) if isinstance(item, dict) else item for item in value]
    if not isinstance(value, dict):
        return value

    normalized = _normalize_item(value)
    for container in containers:
        nested = normalized.get(_normalized_key(container))
        if nested not in (None, "", [], {}) and nested is not value:
            return _normalize_collection(
                nested,
                containers=containers,
                item_keys=item_keys,
                label_key=label_key,
            )

    if any(normalized.get(_normalized_key(key)) not in (None, "", [], {}) for key in item_keys):
        return normalized

    if value and all(isinstance(item, dict) for item in value.values()):
        items = []
        for label, item in value.items():
            copied = _normalize_item(item)
            if not copied.get(label_key):
                copied[label_key] = str(label)
            items.append(copied)
        return items
    return normalized


def _normalize_item(item):
    normalized = {_normalized_key(key): value for key, value in item.items()}
    aliases = {
        "job_title": "title",
        "position_title": "title",
        "company_name": "company",
        "employer_name": "employer",
        "organization_name": "organization",
        "school_name": "school",
        "institution_name": "institution",
        "degree_name": "degree",
        "date_range": "dates",
        "start": "start_date",
        "end": "end_date",
        "details": "description",
        "duties": "responsibilities",
        "highlights": "achievements",
    }
    for source, target in aliases.items():
        if normalized.get(source) not in (None, "", [], {}) and not normalized.get(target):
            normalized[target] = normalized[source]
    return normalized


def _best_resume_mapping(raw):
    """Find the most resume-like mapping inside common AI response wrappers."""
    root = _mapping(raw)
    if root is None:
        return {}

    queue = deque([(root, 0)])
    candidates = []
    seen = set()
    while queue:
        current, depth = queue.popleft()
        if id(current) in seen or depth > 4:
            continue
        seen.add(id(current))
        normalized = {_normalized_key(key): value for key, value in current.items()}
        score = sum(
            1 for key in _CONTENT_KEYS
            if normalized.get(key) not in (None, "", [], {})
        )
        candidates.append((score, -depth, current))
        for key, value in normalized.items():
            if key in _CONTAINER_KEYS:
                nested = _mapping(value)
                if nested is not None:
                    queue.append((nested, depth + 1))

    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def normalize_resume_for_view(raw) -> dict:
    """Map current, legacy, nested, and JSON Resume shapes to the UI schema."""
    selected = _best_resume_mapping(raw)
    if not selected:
        return {}

    fields = {
        _normalized_key(key): value
        for key, value in selected.items()
        if not str(key).startswith("_")
    }

    def first(*names):
        for name in names:
            value = fields.get(_normalized_key(name))
            if value not in (None, "", [], {}):
                return value
        return None

    personal = first(
        "personal_info", "personal_information", "contact_info", "basics"
    )
    personal = personal if isinstance(personal, dict) else {}
    name = (
        first("name", "full_name", "candidate_name")
        or personal.get("name")
        or personal.get("full_name")
    )
    contact = first("links", "contact", "contact_details")
    if not contact:
        contact = {
            key: value for key, value in personal.items()
            if _normalized_key(key) not in {"name", "full_name", "summary"}
            and value not in (None, "", [], {})
        }

    summary = first(
        "summary", "professional_summary", "career_summary", "objective", "profile"
    ) or personal.get("summary")
    if isinstance(summary, list):
        summary = "\n".join(str(item) for item in summary if item not in (None, ""))
    elif isinstance(summary, dict):
        summary = summary.get("text") or summary.get("content") or summary.get("summary")

    education = _normalize_collection(
        first("education", "academic_background", "academic_history"),
        containers=("entries", "items", "schools", "degrees", "education_history", "education"),
        item_keys=("institution", "school", "university", "degree", "program", "title"),
        label_key="institution",
    )
    experience = _normalize_collection(
        first(
            "experience", "work_experience", "professional_experience", "employment",
            "employment_history", "work_history", "work",
        ),
        containers=(
            "entries", "items", "jobs", "positions", "roles", "history", "career",
            "experience", "work_experience", "professional_experience", "employment",
            "employment_history", "work_history", "work",
        ),
        item_keys=(
            "title", "position", "role", "company", "employer", "organization",
            "start_date", "end_date", "dates", "duration", "description",
            "responsibilities", "achievements", "bullets",
        ),
        label_key="company",
    )
    projects = _normalize_collection(
        first("projects", "project_experience", "personal_projects"),
        containers=("entries", "items", "projects"),
        item_keys=("name", "title", "description", "summary", "technologies", "tech"),
        label_key="name",
    )
    certifications = _normalize_collection(
        first("certifications", "certificates", "licenses", "credentials"),
        containers=("entries", "items", "certifications", "certificates", "licenses"),
        item_keys=("name", "title", "issuer", "date", "year"),
        label_key="name",
    )

    normalized = {
        "name": name,
        "summary": summary,
        "contact": contact,
        "education": education,
        "skills": first("skills", "technical_skills", "core_skills", "competencies"),
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
    }
    return {
        key: value for key, value in normalized.items()
        if value not in (None, "", [], {})
    }


def has_structured_resume_content(normalized: dict) -> bool:
    """Return true when the AI view has more than identity/contact data to show."""
    return any(
        normalized.get(key) not in (None, "", [], {})
        for key in (
            "summary", "education", "skills", "experience", "projects", "certifications"
        )
    )
