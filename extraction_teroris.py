import re
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class ExtractionResult:
    value: any
    confidence: float
    source: str

class ImprovedCourtDecisionExtractor:
    def __init__(self, text: str, verbose: bool = True):
        self.raw_text = text
        self.text = self._preprocess_text(text)
        self.data = self._init_structure()
        self.verbose = verbose

    def _preprocess_text(self, text: str) -> str:
        """
        Improved text preprocessing that preserves context
        
        v1.0 problem: Aggressive cleaning removed important context
        v2.0 fix: Smarter cleaning that keeps structure
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Keep lines with substance
            if len(line) > 2:
                cleaned_lines.append(line)
            # Keep single chars if surrounded by meaningful content
            elif len(line) == 1 and i > 0 and i < len(lines) - 1:
                if len(lines[i-1].strip()) > 3 and len(lines[i+1].strip()) > 3:
                    cleaned_lines.append(line)
        
        # Join with newlines to preserve structure
        text = '\n'.join(cleaned_lines)
        
        # Normalize whitespace but keep newlines
        text = re.sub(r' +', ' ', text)
        
        return text
    
    def _init_structure(self) -> Dict:
        """Initialize enhanced data structure with confidence tracking"""
        return {
            "case_id": None,
            "what": {},
            # "when": {},
            # "where": {},
            # "who": {},
            # "why": {},
            # "how": {},
            # "how_much": {},
            "metadata": {
                "extraction_version": "2.0",
                "extraction_date": datetime.now().isoformat(),
                "confidence_scores": {}
            }
        }
    
    def _add_field(self, category: str, field: str, value: any, 
                   confidence: float = 1.0, source: str = "regex"):
        """Add field with confidence tracking"""
        if value is not None:
            self.data[category][field] = value
            self.data["metadata"]["confidence_scores"][f"{category}.{field}"] = {
                "confidence": confidence,
                "source": source
            }
    
    def log(self, message: str):
        """Log extraction progress"""
        if self.verbose:
            print(message)

    # ========= WHAT =========
    def extract_what(self):
        """Extract WHAT with improved patterns"""
        self.log("\n1. EXTRACTING WHAT...")

        patterns = [
            r'Nomor\s*:?\s*([0-9]+/[A-Za-z0-9.\-/ ]+)',
            r'Perkara\s+Nomor\s*:?\s*([0-9]+/[A-Za-z0-9.\-/ ]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                case_num = match.group(1).strip()
                self.data["case_id"] = case_num.replace(" ", "_").replace("/", "_")
                self._add_field("what", "case_number", case_num, 1.0)
                self.log(f"  ✅ Case Number: {case_num}")
                break

        # court name
        court_patterns = [
            r'(Pengadilan\s+Negeri\s+[A-Za-z\s]+?)(?:\s+yang|\s+Nomor|\s+tanggal|\s+Kelas)'
        ]

        for pattern in court_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                court_name = match.group(1).strip()
                self._add_field("what", "court_name", court_name, 0.95)
                self.log(f"  ✅ Court Name: {court_name}")
                break

        # court level
        level_pattern = re.search(
            r'(?:dalam|pada)?\s*(?:pemeriksaan\s+)?tingkat\s+(pertama|banding|kasasi)',
            self.text,
            re.IGNORECASE
        )

        if level_pattern:
            level_word = level_pattern.group(1).lower()
            court_level = f"tingkat_{level_word}" if level_word == "pertama" else level_word

            self._add_field("what", "court_level", court_level, 0.98)
            self.log(f"  ✅ Court Level: {court_level}")

        # indictment model
        for match in re.finditer(r'dakwaan', self.text, re.IGNORECASE):
            start = max(0, match.start() - 150)
            end = match.end() + 150
            window = self.text[start:end].lower()
            
            model_match = re.search(
                r'(tunggal|alternatif|kumulatif|subsider|subsidair|alternative)',
                window
            )
            
            if model_match:
                model = model_match.group(1)
                self._add_field("what", "indictment_model", model, 0.97)
                self.log(f"  ✅ Indictment Model (window): {model}")
                break

        # charged articles
        charges = []

        pattern1 = r'Pasal\s+(\d+)\s+(?:Ayat\s+\((\d+)\)\s*)?(?:huruf\s+([a-z]))?\s*(?:jo\.|juncto)?'
        for match in re.finditer(pattern1, self.text, re.IGNORECASE):
            article = f"Pasal {match.group(1)}"
            if match.group(2):
                article += f" Ayat ({match.group(2)})"
            if match.group(3):
                article += f" huruf {match.group(3)}"
            if article not in charges:
                charges.append(article)
        
        if charges:
            self._add_field("what", "charges", charges[:5], 0.95)
            self.log(f"  ✅ Charges: {len(charges)} pasal found")

        # proven offence
        for match in re.finditer(r'menyatakan', self.text, re.IGNORECASE):
            start = match.start()
            window = self.text[start:start+500]
            
            pasal_match = re.search(
                r'Pasal\s+[0-9A-Za-z\s\.]+(?:jo\.?\s*Pasal\s+[0-9A-Za-z\s\.]+)?',
                window,
                re.IGNORECASE
            )
            
            if pasal_match:
                proven = pasal_match.group(0).strip()
                self._add_field("what", "proven_offence", proven, 0.97)
                self.log(f"  ✅ Proven Offence: {proven}")
                break

    def extract_all(self) -> Dict:
        """Extract all categories and return complete data"""
        self.log("="*60)
        self.log("STARTING IMPROVED EXTRACTION (v2.0)")
        self.log("="*60)
        
        self.extract_what()
        
        self.log("\n" + "="*60)
        self.log("EXTRACTION COMPLETE")
        self.log("="*60)
        
        return self.data

    def get_confidence_report(self) -> Dict:
        """Generate confidence report"""
        scores = self.data["metadata"]["confidence_scores"]
        
        # Calculate average confidence per category
        category_scores = {}
        for field, score_info in scores.items():
            category = field.split('.')[0]
            if category not in category_scores:
                category_scores[category] = []
            category_scores[category].append(score_info['confidence'])
        
        avg_scores = {
            cat: sum(scores) / len(scores)
            for cat, scores in category_scores.items()
        }
        
        # Overall confidence
        all_confidences = [s['confidence'] for s in scores.values()]
        overall = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        
        return {
            "overall_confidence": overall,
            "category_confidence": avg_scores,
            "total_fields": len(scores),
            "high_confidence_fields": sum(1 for s in scores.values() if s['confidence'] >= 0.9),
            "medium_confidence_fields": sum(1 for s in scores.values() if 0.7 <= s['confidence'] < 0.9),
            "low_confidence_fields": sum(1 for s in scores.values() if s['confidence'] < 0.7)
        }
    
    def to_json(self, indent=2) -> str:
        """Convert to JSON"""
        return json.dumps(self.data, indent=indent, ensure_ascii=False)
    
    def save_json(self, filepath: str):
        """Save to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        print(f"\n💾 Saved to: {filepath}")


# ========== TESTING FUNCTION ==========
def test_extractor(pdf_text_file: str, output_json: str = None):
    """Test the improved extractor"""
    
    # Read text
    with open(pdf_text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Extract
    extractor = ImprovedCourtDecisionExtractor(text, verbose=True)
    data = extractor.extract_all()
    
    # Confidence report
    print("\n" + "="*60)
    print("CONFIDENCE REPORT")
    print("="*60)
    
    report = extractor.get_confidence_report()
    print(f"Overall Confidence: {report['overall_confidence']:.1%}")
    print(f"Total Fields Extracted: {report['total_fields']}")
    print(f"  - High Confidence (≥90%): {report['high_confidence_fields']}")
    print(f"  - Medium Confidence (70-90%): {report['medium_confidence_fields']}")
    print(f"  - Low Confidence (<70%): {report['low_confidence_fields']}")
    
    print("\nPer Category:")
    for category, score in sorted(report['category_confidence'].items()):
        print(f"  - {category.upper()}: {score:.1%}")
    
    # Save
    if output_json:
        extractor.save_json(output_json)
    
    return data, report


# ========== MAIN ==========
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "extraction_result_v2.json"
    else:
        # Default test
        input_file = "../Cleaned-Doc/putusan_teroris.txt"
        output_file = "../extract_result_teroris.json"
    
    print(f"📄 Input: {input_file}")
    print(f"💾 Output: {output_file}\n")
    
    data, report = test_extractor(input_file, output_file)
    
    print(f"\n✅ Extraction complete! Check {output_file}")


        
