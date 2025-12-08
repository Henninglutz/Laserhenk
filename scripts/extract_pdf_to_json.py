"""
Extract text from PDFs and convert to structured JSON for RAG import

Dieses Script:
1. Liest PDFs mit PyPDF2 oder pdfplumber
2. Extrahiert Text mit Struktur (Überschriften, Sections)
3. Erstellt JSON-Chunks für RAG-Import
4. Optional: OCR für gescannte PDFs

Usage:
    python scripts/extract_pdf_to_json.py \
        --input docs/source_pdfs/hemden_katalog.pdf \
        --output drive_mirror/henk/shirts/hemden_chunks.json \
        --category shirts \
        --chunk-size 500

Requirements:
    pip install pypdf2 pdfplumber
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import re

try:
    import pdfplumber
except ImportError:
    print("❌ pdfplumber nicht installiert!")
    print("   Installiere mit: pip install pdfplumber")
    sys.exit(1)


class PDFExtractor:
    """Extrahiert strukturierten Text aus PDFs."""

    def __init__(self, chunk_size: int = 500):
        """
        Initialize the extractor.

        Args:
            chunk_size: Maximum characters per chunk
        """
        self.chunk_size = chunk_size

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract all text from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        print(f"📄 Lese PDF: {pdf_path}")

        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            print(f"   Seiten: {len(pdf.pages)}")

            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Seite {i} ---\n{page_text}\n"

        print(f"✅ Text extrahiert: {len(text)} Zeichen")
        return text

    def chunk_text(self, text: str, category: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks for RAG.

        Args:
            text: Full text to chunk
            category: Category (shirts, styles, pricing)

        Returns:
            List of chunk dicts
        """
        print(f"🔪 Chunking Text (max {self.chunk_size} chars pro Chunk)...")

        # Split by paragraphs (double newlines)
        paragraphs = text.split("\n\n")

        chunks = []
        current_chunk = ""
        chunk_num = 1

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk_size, save current chunk
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append(
                    {
                        "chunk_id": f"{category}_chunk_{chunk_num}",
                        "category": category,
                        "content": current_chunk.strip(),
                        "char_count": len(current_chunk),
                    }
                )
                chunk_num += 1
                current_chunk = para
            else:
                current_chunk += f"\n\n{para}"

        # Add last chunk
        if current_chunk:
            chunks.append(
                {
                    "chunk_id": f"{category}_chunk_{chunk_num}",
                    "category": category,
                    "content": current_chunk.strip(),
                    "char_count": len(current_chunk),
                }
            )

        print(f"✅ Erstellt: {len(chunks)} Chunks")
        return chunks

    def detect_sections(self, text: str) -> Dict[str, str]:
        """
        Detect sections in text (simple heuristic).

        Args:
            text: Full text

        Returns:
            Dict of section_name -> content
        """
        # Simple detection: Lines in ALL CAPS or with numbers
        section_pattern = r"^([A-ZÄÖÜ\s\d\.]+)$"

        sections = {}
        current_section = "introduction"
        current_content = ""

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check if this is a section header
            if re.match(section_pattern, line) and len(line) > 3:
                # Save previous section
                if current_content:
                    sections[current_section] = current_content.strip()
                # Start new section
                current_section = line.lower().replace(" ", "_")
                current_content = ""
            else:
                current_content += f"{line}\n"

        # Save last section
        if current_content:
            sections[current_section] = current_content.strip()

        return sections


def main():
    """Main extraction function."""
    parser = argparse.ArgumentParser(
        description="Extract text from PDF and convert to JSON chunks"
    )
    parser.add_argument("--input", required=True, help="Input PDF file path")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument(
        "--category",
        required=True,
        choices=["shirts", "styles", "pricing", "fabrics"],
        help="Content category",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500, help="Max characters per chunk"
    )
    parser.add_argument(
        "--detect-sections",
        action="store_true",
        help="Try to detect sections in PDF",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("📄 PDF EXTRACTION TO JSON")
    print("=" * 70)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Category: {args.category}")
    print(f"Chunk Size: {args.chunk_size}")
    print()

    # Check input exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Fehler: PDF nicht gefunden: {input_path}")
        sys.exit(1)

    # Initialize extractor
    extractor = PDFExtractor(chunk_size=args.chunk_size)

    # Extract text
    text = extractor.extract_text(input_path)

    # Optional: Detect sections
    if args.detect_sections:
        print("\n🔍 Erkenne Sections...")
        sections = extractor.detect_sections(text)
        print(f"✅ Gefunden: {len(sections)} Sections")
        for section_name in sections.keys():
            print(f"   - {section_name}")
        print()

    # Create chunks
    chunks = extractor.chunk_text(text, args.category)

    # Prepare output
    output_data = {
        "meta": {
            "source_file": str(input_path.name),
            "category": args.category,
            "total_chunks": len(chunks),
            "chunk_size": args.chunk_size,
            "total_chars": len(text),
        },
        "chunks": chunks,
    }

    # Save to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ JSON gespeichert: {output_path}")
    print(f"   Total Chunks: {len(chunks)}")
    print(f"   Durchschnitt: {len(text) // len(chunks)} chars pro Chunk")
    print()
    print("🎯 Nächster Schritt:")
    print(f"   python scripts/import_json_to_rag.py --input {output_path}")


if __name__ == "__main__":
    main()
