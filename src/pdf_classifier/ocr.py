"""OCR module using Nitro PDF Pro via AppleScript."""

import subprocess
import time
from pathlib import Path


def needs_ocr(pdf_path: Path) -> bool:
    """Check if a PDF needs OCR by trying to extract text."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages[:2]:  # Check first 2 pages
            text += page.extract_text() or ""
        return len(text.strip()) < 50
    except Exception:
        return True


def run_ocr(pdf_path: Path, timeout: int = 120) -> bool:
    """
    Run OCR on a PDF using Nitro PDF Pro via AppleScript.

    Returns True if OCR was successful, False otherwise.
    """
    pdf_path = Path(pdf_path).resolve()

    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return False

    # Open PDF in Nitro PDF Pro
    open_cmd = ["open", "-a", "Nitro PDF Pro", str(pdf_path)]
    try:
        subprocess.run(open_cmd, check=True, capture_output=True)
        time.sleep(3)  # Wait for app to open file
    except subprocess.CalledProcessError as e:
        print(f"Error opening PDF: {e}")
        return False

    # Run OCR via AppleScript
    applescript = '''
    tell application "Nitro PDF Pro"
        if (count of documents) > 0 then
            set theDoc to document 1
            if needs ocr of theDoc then
                ocr theDoc
                repeat while performing ocr of theDoc
                    delay 1
                end repeat
                save theDoc
                close theDoc
                return "success"
            else
                close theDoc
                return "no_ocr_needed"
            end if
        else
            return "no_document"
        end if
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()

        if output == "success":
            print(f"OCR completed: {pdf_path.name}")
            return True
        elif output == "no_ocr_needed":
            print(f"No OCR needed: {pdf_path.name}")
            return True
        else:
            print(f"OCR failed: {output}")
            return False

    except subprocess.TimeoutExpired:
        print(f"OCR timeout for: {pdf_path.name}")
        # Try to close the document
        subprocess.run(
            ["osascript", "-e", 'tell application "Nitro PDF Pro" to close document 1'],
            capture_output=True
        )
        return False
    except Exception as e:
        print(f"OCR error: {e}")
        return False


def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""
