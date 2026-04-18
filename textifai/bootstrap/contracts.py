from __future__ import annotations

from dataclasses import dataclass, field


BOOTSTRAP_MODE_CATALOG = (
    "new_project",
    "import_into_existing_vault",
)

BOOTSTRAP_ARTIFACT_TYPE_CATALOG = (
    "character",
    "lore",
    "scene",
    "chapter",
    "mixed_note",
    "project_note",
)

BOOTSTRAP_IMPORT_MODE_CATALOG = (
    "literal_copy",
    "literal_segmented",
    "light_structural_normalization",
)

BOOTSTRAP_FRAGMENT_STATUS_CATALOG = (
    "draft",
    "needs_review",
)

BOOTSTRAP_LANGUAGE_HINT_CATALOG = (
    "mixed",
    "unknown",
)


@dataclass(frozen=True)
class VaultInitializationConfig:
    vault_root: str
    mode: str
    project_title: str | None = None
    primary_language: str | None = None
    working_languages: list[str] = field(default_factory=list)
    create_base_structure: bool = True
    use_import_staging: bool = True

    def __post_init__(self) -> None:
        _ensure_catalog_value("mode", self.mode, BOOTSTRAP_MODE_CATALOG)


@dataclass(frozen=True)
class SourceDocumentRecord:
    source_id: str
    path: str
    relative_path: str
    filename: str
    extension: str
    size_bytes: int
    checksum: str
    dominant_language: str | None
    detected_languages: list[str] = field(default_factory=list)
    has_mixed_language: bool = False
    likely_content_kinds: list[str] = field(default_factory=list)
    line_count: int = 0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.extension.lower() not in {"md", "txt"}:
            raise ValueError(f"Unsupported extension: {self.extension}")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        if self.line_count < 0:
            raise ValueError("line_count must be non-negative")


@dataclass(frozen=True)
class SourceDocumentInventory:
    source_root: str
    documents: list[SourceDocumentRecord] = field(default_factory=list)
    total_documents: int = 0
    total_bytes: int = 0
    detected_working_languages: list[str] = field(default_factory=list)
    has_multilingual_material: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceFragment:
    fragment_id: str
    source_id: str
    char_start: int
    char_end: int
    text: str
    literal_text_hash: str
    detected_kind: str
    kind_confidence: float
    language: str | None
    has_mixed_language: bool = False
    register_signals: list[str] = field(default_factory=list)
    needs_review: bool = False

    def __post_init__(self) -> None:
        if self.char_start < 0 or self.char_end < self.char_start:
            raise ValueError("Invalid fragment character range")
        if self.char_end == self.char_start and self.text.strip():
            raise ValueError("Non-empty fragments must have a positive character range")
        if not 0.0 <= self.kind_confidence <= 1.0:
            raise ValueError("kind_confidence must be between 0 and 1")


@dataclass(frozen=True)
class ImportProvenance:
    source_id: str
    source_path: str
    source_checksum: str
    fragment_ids: list[str] = field(default_factory=list)
    char_ranges: list[dict[str, int]] = field(default_factory=list)
    import_mode: str = "literal_copy"
    llm_assisted: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ensure_catalog_value("import_mode", self.import_mode, BOOTSTRAP_IMPORT_MODE_CATALOG)


@dataclass(frozen=True)
class NormalizedArtifactDraft:
    draft_id: str
    artifact_type: str
    title: str
    slug: str
    target_path: str
    body: str
    dominant_language: str | None
    detected_languages: list[str] = field(default_factory=list)
    register_signals: list[str] = field(default_factory=list)
    provenance: ImportProvenance | None = None
    normalization_notes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "draft"

    def __post_init__(self) -> None:
        _ensure_catalog_value("artifact_type", self.artifact_type, BOOTSTRAP_ARTIFACT_TYPE_CATALOG)
        _ensure_catalog_value("status", self.status, BOOTSTRAP_FRAGMENT_STATUS_CATALOG)
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.slug.strip():
            raise ValueError("slug must not be empty")
        if not self.target_path.strip():
            raise ValueError("target_path must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class NormalizationPlan:
    plan_id: str
    target_vault_root: str
    target_staging_root: str
    drafts: list[NormalizedArtifactDraft] = field(default_factory=list)
    unmapped_fragments: list[str] = field(default_factory=list)
    ambiguous_fragments: list[str] = field(default_factory=list)
    coverage_summary: dict[str, int] = field(default_factory=dict)
    requires_confirmation: bool = True


@dataclass(frozen=True)
class LanguageProfile:
    project_primary_language: str | None
    working_languages: list[str] = field(default_factory=list)
    document_languages: dict[str, list[str]] = field(default_factory=dict)
    fragment_languages: dict[str, str] = field(default_factory=dict)
    has_multilingual_documents: bool = False
    register_signals_by_language: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class BootstrapResult:
    vault_root: str
    staging_root: str | None
    created_vault: bool
    inventory: SourceDocumentInventory | None
    normalization_plan: NormalizationPlan | None
    written_drafts: list[str] = field(default_factory=list)
    coverage_report: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _ensure_catalog_value(field_name: str, value: str, catalog: tuple[str, ...]) -> None:
    if value not in catalog:
        raise ValueError(f"Unsupported {field_name}: {value}")
