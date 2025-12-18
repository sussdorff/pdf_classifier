"""Semantic document analyzer using Claude Code CLI (Max Plan)."""

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class ClassificationResult:
    """Result of document classification."""
    category: str  # e.g., "cognovis", "privat", "agiler_norden"
    subcategory: str  # e.g., "buchhaltung", "versicherung"
    company: str  # e.g., "Continentale", "Hiscox"
    doc_type: str  # e.g., "Rechnung", "Versicherungsschein"
    doc_date: str  # ISO format date from document
    title: str  # Brief descriptive title
    destination: str  # Full destination path
    new_filename: str  # Suggested new filename
    confidence: str  # "high", "medium", "low"
    reasoning: str  # Why this classification


def load_rules(rules_path: Path | None = None) -> dict:
    """Load classification rules from JSON file."""
    if rules_path is None:
        rules_path = Path(__file__).parent.parent.parent / "rules.json"

    with open(rules_path) as f:
        return json.load(f)


def analyze_document(text: str, filename: str, rules: dict | None = None) -> ClassificationResult:
    """
    Analyze document text using Claude Code CLI and return classification.

    Uses the user's Claude Max subscription via the `claude` CLI.

    Args:
        text: Extracted text from the PDF
        filename: Original filename of the PDF
        rules: Optional rules dict, loaded from rules.json if not provided

    Returns:
        ClassificationResult with all classification details
    """
    if rules is None:
        rules = load_rules()

    # Build context about available categories and companies
    categories_info = json.dumps(rules["categories"], indent=2, ensure_ascii=False)
    companies_info = json.dumps(rules["companies"], indent=2, ensure_ascii=False)

    prompt = f"""Analysiere dieses deutsche Dokument und klassifiziere es.

VERFÜGBARE KATEGORIEN UND ZIELORDNER:
{categories_info}

BEKANNTE FIRMEN UND IHRE ZUORDNUNG:
{companies_info}

DOKUMENT-DATEINAME: {filename}

DOKUMENT-TEXT (erste 3000 Zeichen):
{text[:3000]}

---

Antworte NUR mit einem JSON-Objekt in diesem Format (kein Markdown, kein Code-Block, nur das JSON):
{{
    "category": "cognovis|privat|agiler_norden|haus|flying_hamburger",
    "subcategory": "buchhaltung|versicherung|krankenversicherung|arztrechnung|berufsunfaehigkeit|vermoegen|kfz|steuer|nebenkosten",
    "company": "Firmenname aus dem Dokument",
    "doc_type": "Rechnung|Versicherungsschein|Leistungsabrechnung|Beitragsrechnung|etc.",
    "doc_date": "YYYY-MM-DD (Datum aus dem Dokument)",
    "title": "Kurze beschreibende Überschrift (2-4 Wörter)",
    "confidence": "high|medium|low",
    "reasoning": "Kurze Begründung"
}}

WICHTIGE REGELN:
1. "cognovis GmbH" oder "Schrödersweg 27" als EMPFÄNGER → category: "cognovis"
2. "Agiler Norden" → category: "agiler_norden"
3. Privat für "Malte Sussdorff" → category: "privat"
4. doc_date = DOKUMENTDATUM (nicht heute)
5. title soll beschreibend sein: "Beitragsrechnung 2026", "Dynamiknachtrag"

NUR JSON ausgeben!"""

    # Call claude CLI with --print flag for non-interactive output
    try:
        result = subprocess.run(
            ["claude", "--print", "--model", "haiku", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        response_text = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return _fallback_result(filename, "Claude CLI timeout")
    except FileNotFoundError:
        return _fallback_result(filename, "Claude CLI not found - install with: npm install -g @anthropic-ai/claude-code")
    except Exception as e:
        return _fallback_result(filename, f"Claude CLI error: {e}")

    # Parse JSON response
    try:
        # Handle potential markdown code blocks
        if "```" in response_text:
            # Extract JSON from code block
            parts = response_text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    response_text = part
                    break

        # Find JSON object in response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            response_text = response_text[start:end]

        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        return _fallback_result(filename, f"JSON parsing failed: {e}\nResponse: {response_text[:200]}")

    # Build destination path
    destination = _build_destination(parsed, rules)
    new_filename = _build_filename(parsed)

    return ClassificationResult(
        category=parsed.get("category", "unknown"),
        subcategory=parsed.get("subcategory", "unknown"),
        company=parsed.get("company", "Unknown"),
        doc_type=parsed.get("doc_type", "Dokument"),
        doc_date=parsed.get("doc_date", date.today().isoformat()),
        title=parsed.get("title", "Dokument"),
        destination=destination,
        new_filename=new_filename,
        confidence=parsed.get("confidence", "medium"),
        reasoning=parsed.get("reasoning", "")
    )


def _fallback_result(filename: str, reason: str) -> ClassificationResult:
    """Return a fallback result when classification fails."""
    return ClassificationResult(
        category="unknown",
        subcategory="unknown",
        company="Unknown",
        doc_type="Dokument",
        doc_date=date.today().isoformat(),
        title="Unklassifiziert",
        destination="~/Documents/Scans",
        new_filename=filename,
        confidence="low",
        reasoning=reason
    )


def _build_destination(parsed: dict, rules: dict) -> str:
    """Build the destination path from parsed classification."""
    category = parsed.get("category", "unknown")
    subcategory = parsed.get("subcategory", "unknown")
    company = parsed.get("company", "")
    doc_date = parsed.get("doc_date", "")

    category_info = rules["categories"].get(category, {})
    base_path = category_info.get("base", "~/Documents")

    subcategory_info = category_info.get("subcategories", {}).get(subcategory, {})
    if isinstance(subcategory_info, dict):
        sub_path = subcategory_info.get("path", "")
    else:
        sub_path = ""

    # Handle year placeholder in path
    if "{year}" in sub_path:
        year = doc_date[:4] if doc_date else str(date.today().year)
        sub_path = sub_path.replace("{year}", year)

    # Check for company-specific subfolder
    company_info = rules["companies"].get(company, {})
    subfolder = company_info.get("subfolder", "")

    if subfolder:
        destination = f"{base_path}/{sub_path}/{subfolder}" if sub_path else f"{base_path}/{subfolder}"
    elif sub_path:
        destination = f"{base_path}/{sub_path}"
    else:
        destination = base_path

    # Clean up double slashes
    return destination.replace("//", "/")


def _build_filename(parsed: dict) -> str:
    """Build the new filename from parsed classification."""
    doc_date = parsed.get("doc_date", date.today().isoformat())
    category = parsed.get("category", "unknown").replace("_", " ")
    subcategory = parsed.get("subcategory", "unknown").replace("_", " ")
    company = parsed.get("company", "Unknown")
    title = parsed.get("title", "Dokument")

    return f"{doc_date} - {category} - {subcategory} - {company} {title}.pdf"
