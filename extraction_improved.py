#!/usr/bin/env python3
"""
IMPROVED Court Decision Data Extraction - 5W+2H Framework
Version: 2.0 (Improved from v1.0 with 64% → 85%+ accuracy target)

Improvements:
1. Fixed defendant name extraction (critical bug)
2. Fixed subsidair pattern
3. Added nationality extraction
4. Added prosecutor extraction  
5. Better text cleaning
6. Improved evidence types detection
7. Added court fees extraction
8. Added confidence scoring
9. Better error handling
10. More flexible regex patterns

Author: AI Assistant
Date: 2026-02-16
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class ExtractionResult:
    """Data class for extraction results with confidence"""
    value: any
    confidence: float  # 0.0 to 1.0
    source: str  # Where this data came from

class ImprovedCourtDecisionExtractor:
    """Improved extractor with higher accuracy and confidence scoring"""
    
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
            "when": {},
            "where": {},
            "who": {},
            "why": {},
            "how": {},
            "how_much": {},
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
    
    # ========== 1. WHAT (APA) ==========
    def extract_what(self):
        """Extract WHAT with improved patterns"""
        self.log("\n1️⃣ EXTRACTING WHAT...")
        
        # Case number - improved pattern
        patterns = [
            r'Nomor\s+(\d+\s*[A-Z]?/[A-Za-z.\s]+/\d{4})',
            r'Perkara\s+Nomor\s+(\d+\s*[A-Z]?/[A-Za-z.]+/\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                case_num = match.group(1).strip()
                self.data["case_id"] = case_num.replace(" ", "_").replace("/", "_")
                self._add_field("what", "case_number", case_num, 1.0)
                self.log(f"  ✅ Case Number: {case_num}")
                break
        
        # Case type
        if re.search(r'Tindak\s+Pidana\s+Khusus|Pid\.Sus', self.text, re.IGNORECASE):
            self._add_field("what", "case_type", "Tindak Pidana Khusus", 0.95)
            self.log("  ✅ Case Type: Tindak Pidana Khusus")
        elif re.search(r'Pidana\s+Umum|Pid\.', self.text, re.IGNORECASE):
            self._add_field("what", "case_type", "Pidana Umum", 0.9)
            self.log("  ✅ Case Type: Pidana Umum")
        
        # Category - improved detection
        categories = {
            "Narkotika": r'(?:narkotika|sabu|ganja|ekstasi|psikotropika)',
            "Korupsi": r'korupsi|suap|gratifikasi',
            "Terorisme": r'teror|bom|radikalis',
            "Pencucian Uang": r'(?:TPPU|pencucian\s+uang|money\s+laundering)',
            "Kehutanan": r'kehutanan|illegal\s+logging',
            "Perikanan": r'perikanan|illegal\s+fishing'
        }
        
        for category, pattern in categories.items():
            if re.search(pattern, self.text, re.IGNORECASE):
                self._add_field("what", "category", category, 0.9)
                self.log(f"  ✅ Category: {category}")
                break
        
        # Charges - improved to capture more variations
        charges = []
        
        # Pattern 1: Standard format
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
        
        # Verdict type - improved patterns
        verdict_patterns = [
            (r'terbukti\s+(?:secara\s+)?(?:sah\s+dan\s+)?(?:meyakinkan\s+)?bersalah', "Bersalah", 0.98),
            (r'tidak\s+terbukti', "Tidak Terbukti", 0.98),
            (r'lepas\s+dari\s+segala\s+tuntutan', "Lepas", 0.98),
            (r'bebas', "Bebas", 0.95)
        ]
        
        for pattern, verdict, conf in verdict_patterns:
            if re.search(pattern, self.text, re.IGNORECASE):
                self._add_field("what", "verdict_type", verdict, conf)
                self.log(f"  ✅ Verdict: {verdict}")
                break
        
        # Status
        if re.search(r'kasasi', self.text, re.IGNORECASE):
            self._add_field("what", "status", "Kasasi", 0.98)
            self.log("  ✅ Status: Kasasi")
        elif re.search(r'banding', self.text, re.IGNORECASE):
            self._add_field("what", "status", "Banding", 0.98)
            self.log("  ✅ Status: Banding")
        elif re.search(r'Pengadilan\s+Negeri', self.text, re.IGNORECASE):
            self._add_field("what", "status", "Tingkat Pertama", 0.9)
            self.log("  ✅ Status: Tingkat Pertama")
    
    # ========== 2. WHEN (KAPAN) ==========
    def extract_when(self):
        """Extract WHEN with improved date classification"""
        self.log("\n2️⃣ EXTRACTING WHEN...")
        
        # Indonesian months mapping
        months = {
            'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
            'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
        }
        
        # Extract all dates with context
        date_pattern = r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})'
        
        dates_with_context = []
        for match in re.finditer(date_pattern, self.text, re.IGNORECASE):
            date_str = match.group(0)
            # Get context (100 chars before)
            start = max(0, match.start() - 100)
            context = self.text[start:match.start()].lower()
            
            dates_with_context.append({
                'date': date_str,
                'context': context,
                'position': match.start()
            })
        
        self.log(f"  ✅ Found {len(dates_with_context)} dates")
        
        # Classify dates based on context
        for item in dates_with_context:
            date_str = item['date']
            context = item['context']
            
            # Arrest date
            if re.search(r'(?:sejak|tanggal|penangkapan|ditangkap)', context):
                self._add_field("when", "arrest_date", date_str, 0.9)
                self.log(f"  ✅ Arrest Date: {date_str}")
            
            # District court date
            if re.search(r'pengadilan\s+negeri', context):
                self._add_field("when", "district_court_date", date_str, 0.9)
                self.log(f"  ✅ District Court Date: {date_str}")
            
            # High court date
            if re.search(r'pengadilan\s+tinggi', context):
                self._add_field("when", "high_court_date", date_str, 0.9)
                self.log(f"  ✅ High Court Date: {date_str}")
            
            # Birth date
            if re.search(r'(?:lahir|tanggal\s+lahir)', context):
                self._add_field("when", "birth_date", date_str, 0.95)
                self.log(f"  ✅ Birth Date: {date_str}")
        
        # Store all dates for reference
        all_dates = [item['date'] for item in dates_with_context[:15]]
        self._add_field("when", "all_dates", all_dates, 0.95)
    
    # ========== 3. WHERE (DIMANA) ==========
    def extract_where(self):
        """Extract WHERE with improved address parsing"""
        self.log("\n3️⃣ EXTRACTING WHERE...")
        
        # Residence - multiple patterns to try
        residence_patterns = [
            r'Tempat\s+Tinggal\s*:\s*([^;]+?)(?:Agama|Pekerjaan|;)',
            r'Alamat\s*:\s*([^;]+?)(?:Agama|Pekerjaan|;)',
            r'beralamat\s+di\s+([^;]+?)(?:Agama|Pekerjaan|;)'
        ]
        
        for pattern in residence_patterns:
            match = re.search(pattern, self.text, re.DOTALL | re.IGNORECASE)
            if match:
                address = match.group(1).strip()
                address = ' '.join(address.split())  # Normalize whitespace
                
                self._add_field("where", "residence", address, 0.95)
                self.log(f"  ✅ Residence: {address[:80]}...")
                
                # Parse components with improved patterns
                components = {
                    'village': r'(?:Desa|Kelurahan|Dusun)\s+([^,;]+)',
                    'district': r'Kecamatan\s+([^,;]+)',
                    'regency': r'(?:Kabupaten|Kota)\s+([^,;]+)',
                    'province': r'(?:Provinsi\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$'
                }
                
                for comp_name, comp_pattern in components.items():
                    comp_match = re.search(comp_pattern, address, re.IGNORECASE)
                    if comp_match:
                        value = comp_match.group(1).strip()
                        self._add_field("where", comp_name, value, 0.9)
                        self.log(f"     - {comp_name.title()}: {value}")
                
                # Infer province from regency if not explicitly stated
                if "regency" in self.data["where"] and "province" not in self.data["where"]:
                    regency = self.data["where"]["regency"]
                    if "Aceh" in regency:
                        self._add_field("where", "province", "Aceh", 0.8, "inferred")
                        self.log(f"     - Province (inferred): Aceh")
                
                break
        
        # Courts - improved patterns
        court_patterns = {
            'district_court': r'Pengadilan\s+Negeri\s+([A-Za-z\s]+?)(?:\s+Nomor|\s+tanggal|\s+Kelas)',
            'high_court': r'Pengadilan\s+Tinggi\s+([A-Za-z\s]+?)(?:\s+Nomor|\s+tanggal)',
            'supreme_court': r'Mahkamah\s+Agung'
        }
        
        for court_type, pattern in court_patterns.items():
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                if court_type == 'supreme_court':
                    value = "Mahkamah Agung RI"
                else:
                    value = match.group(1).strip()
                    prefix = "PN" if "district" in court_type else "PT"
                    value = f"{prefix} {value}"
                
                self._add_field("where", court_type, value, 0.95)
                self.log(f"  ✅ {court_type.replace('_', ' ').title()}: {value}")
    
    # ========== 4. WHO (SIAPA) ==========
    def extract_who(self):
        """Extract WHO with FIXED defendant name pattern"""
        self.log("\n4️⃣ EXTRACTING WHO...")
        
        # CRITICAL FIX: Defendant name - handle names with initials and dots
        name_patterns = [
            # Pattern 1: With bin/binti (FIXED to handle dots and initials)
            r'Nama\s*:\s*([A-Z][A-Za-z\s\.]+?\s+(?:bin|binti)\s+[A-Z][A-Za-z\s\.]+)',
            # Pattern 2: Without bin/binti
            r'Nama\s*:\s*([A-Z][A-Z\s\.]+?)(?:\s*;|\s*Tempat)',
            # Pattern 3: Terdakwa context
            r'Terdakwa\s+([A-Z][A-Za-z\s\.]+?\s+(?:bin|binti)\s+[A-Z][A-Za-z\s\.]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, self.text)
            if match:
                name = match.group(1).strip()
                # Clean up excessive spaces
                name = ' '.join(name.split())
                self._add_field("who", "defendant_name", name, 0.95)
                self.log(f"  ✅ Defendant Name: {name}")
                break
        else:
            self.log("  ❌ Defendant Name: NOT FOUND")
        
        # Birth place - improved
        birth_patterns = [
            r'Tempat\s+Lahir\s*:\s*([^;]+?)(?:Umur|;)',
            r'lahir\s+di\s+([A-Za-z\s]+?)(?:,|\s+pada)'
        ]
        
        for pattern in birth_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                birth_place = match.group(1).strip()
                self._add_field("who", "birth_place", birth_place, 0.9)
                self.log(f"  ✅ Birth Place: {birth_place}")
                break
        
        # Age and birth date - improved pattern
        age_pattern = r'(?:Umur[^:]*:\s*)?(\d+)\s+tahun[/\s]+(\d{1,2}\s+\w+\s+\d{4})'
        match = re.search(age_pattern, self.text, re.IGNORECASE)
        if match:
            age = int(match.group(1))
            birth_date = match.group(2)
            self._add_field("who", "age", age, 0.98)
            self._add_field("who", "birth_date", birth_date, 0.95)
            self.log(f"  ✅ Age: {age} years")
            self.log(f"  ✅ Birth Date: {birth_date}")
        
        # Gender - improved
        gender_match = re.search(r'Jenis\s+Kelamin\s*:\s*(Laki-laki|Perempuan)', 
                                self.text, re.IGNORECASE)
        if gender_match:
            gender = gender_match.group(1)
            self._add_field("who", "gender", gender, 0.99)
            self.log(f"  ✅ Gender: {gender}")
        
        # FIXED: Nationality extraction
        nationality_patterns = [
            r'Kewarganegaraan\s*:\s*(\w+)',
            r'berkewarganegaraan\s+(\w+)'
        ]
        
        for pattern in nationality_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                nationality = match.group(1).strip()
                self._add_field("who", "nationality", nationality, 0.95)
                self.log(f"  ✅ Nationality: {nationality}")
                break
        
        # Religion - improved
        religion_patterns = [
            r'Agama\s*:\s*(\w+)',
            r'beragama\s+(\w+)'
        ]
        
        for pattern in religion_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                religion = match.group(1).strip()
                self._add_field("who", "religion", religion, 0.95)
                self.log(f"  ✅ Religion: {religion}")
                break
        
        # Occupation - improved
        occupation_patterns = [
            r'Pekerjaan\s*:\s*([^;]+?)(?:Terdakwa|;|\n)',
            r'bekerja\s+sebagai\s+([^;]+?)(?:;|\n)'
        ]
        
        for pattern in occupation_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                occupation = match.group(1).strip()
                self._add_field("who", "occupation", occupation, 0.9)
                self.log(f"  ✅ Occupation: {occupation}")
                break
        
        # FIXED: Prosecutor extraction
        prosecutor_patterns = [
            r'Kejaksaan\s+Negeri\s+([A-Za-z\s]+)',
            r'Penuntut\s+Umum\s+pada\s+Kejaksaan\s+Negeri\s+([A-Za-z\s]+)',
            r'Jaksa\s+Penuntut\s+Umum\s+pada\s+Kejaksaan\s+Negeri\s+([A-Za-z\s]+)'
        ]
        
        for pattern in prosecutor_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                office = match.group(1).strip()
                prosecutor_info = {
                    "office": f"Kejaksaan Negeri {office}",
                    "type": "Kejaksaan Negeri"
                }
                self._add_field("who", "prosecutor", prosecutor_info, 0.9)
                self.log(f"  ✅ Prosecutor: Kejaksaan Negeri {office}")
                break
    
    # ========== 5. WHY (MENGAPA) ==========
    def extract_why(self):
        """Extract WHY with improved legal basis extraction"""
        self.log("\n5️⃣ EXTRACTING WHY...")
        
        # UU references - improved to capture full text
        uu_pattern = r'Undang-Undang\s+(?:Republik\s+Indonesia\s+)?Nomor\s+(\d+)\s+Tahun\s+(\d{4})\s+tentang\s+([^;\.]+)'
        laws = []
        
        for match in re.finditer(uu_pattern, self.text, re.IGNORECASE):
            law = {
                "number": match.group(1),
                "year": match.group(2),
                "about": match.group(3).strip(),
                "full_ref": f"UU No. {match.group(1)} Tahun {match.group(2)}"
            }
            
            # Avoid duplicates
            if not any(l['full_ref'] == law['full_ref'] for l in laws):
                laws.append(law)
        
        if laws:
            self._add_field("why", "legal_basis", laws[:5], 0.95)
            self.log(f"  ✅ Laws: {len(laws)} UU referenced")
            for law in laws[:3]:
                self.log(f"     - {law['full_ref']}: {law['about'][:50]}...")
        
        # Legal elements - improved extraction
        elements = []
        element_patterns = {
            "Tanpa hak": r'tanpa\s+hak',
            "Melawan hukum": r'melawan\s+hukum',
            "Dengan sengaja": r'dengan\s+sengaja',
            "Menyalahgunakan": r'menyalahgunakan',
            "Memiliki": r'memiliki',
            "Mengedarkan": r'mengedarkan',
            "Menggunakan": r'menggunakan',
            "Menyimpan": r'menyimpan'
        }
        
        for element, pattern in element_patterns.items():
            if re.search(pattern, self.text, re.IGNORECASE):
                elements.append(element)
        
        if elements:
            self._add_field("why", "legal_elements", elements, 0.85)
            self.log(f"  ✅ Legal Elements: {', '.join(elements[:5])}")
    
    # ========== 6. HOW (BAGAIMANA) ==========
    def extract_how(self):
        """Extract HOW with IMPROVED evidence detection"""
        self.log("\n6️⃣ EXTRACTING HOW...")
        
        # Evidence types - FIXED with better patterns
        evidence_types = []
        evidence_patterns = {
            "Keterangan Saksi": [
                r'keterangan\s+saksi',
                r'saksi-saksi',
                r'keterangan\s+dari\s+saksi'
            ],
            "Keterangan Ahli": [
                r'keterangan\s+ahli',
                r'ahli\s+yang\s+memberikan\s+keterangan'
            ],
            "Barang Bukti": [
                r'barang\s+bukti',
                r'benda\s+bukti'
            ],
            "Surat": [
                r'bukti\s+surat',
                r'alat\s+bukti\s+surat'
            ],
            "Keterangan Terdakwa": [
                r'keterangan\s+terdakwa',
                r'keterangan\s+dari\s+terdakwa'
            ],
            "Petunjuk": [
                r'alat\s+bukti\s+petunjuk',
                r'petunjuk\s+sebagai\s+alat\s+bukti'
            ]
        }
        
        for evidence_type, patterns in evidence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, self.text, re.IGNORECASE):
                    if evidence_type not in evidence_types:
                        evidence_types.append(evidence_type)
                    break
        
        if evidence_types:
            self._add_field("how", "evidence_types", evidence_types, 0.9)
            self.log(f"  ✅ Evidence Types: {', '.join(evidence_types)}")
        else:
            self.log("  ⚠️ Evidence Types: None detected")
        
        # Legal process stages
        process = []
        process_stages = {
            "Penangkapan": r'penangkapan|ditangkap',
            "Penahanan": r'penahanan|ditahan',
            "Penyidikan": r'penyidikan|penyelidikan',
            "Penuntutan": r'penuntutan|dakwaan',
            "Persidangan": r'persidangan|sidang',
            "Putusan PN": r'Putusan\s+Pengadilan\s+Negeri',
            "Banding": r'permohonan\s+banding|mengajukan\s+banding',
            "Kasasi": r'permohonan\s+kasasi|mengajukan\s+kasasi'
        }
        
        for stage, pattern in process_stages.items():
            if re.search(pattern, self.text, re.IGNORECASE):
                process.append(stage)
        
        if process:
            self._add_field("how", "legal_process", process, 0.85)
            self.log(f"  ✅ Legal Process: {' → '.join(process[:5])}")
        
        # Modus operandi - basic extraction
        modus_keywords = {
            "Memiliki": r'memiliki.*?narkotika',
            "Menyimpan": r'menyimpan.*?narkotika',
            "Menguasai": r'menguasai.*?narkotika',
            "Menjual": r'menjual|mengedarkan.*?narkotika',
            "Menggunakan": r'menggunakan.*?narkotika',
            "Membeli": r'membeli.*?narkotika'
        }
        
        modus = []
        for action, pattern in modus_keywords.items():
            if re.search(pattern, self.text, re.IGNORECASE):
                modus.append(action)
        
        if modus:
            self._add_field("how", "modus_operandi", modus, 0.75)
            self.log(f"  ✅ Modus Operandi: {', '.join(modus)}")
    
    # ========== 7. HOW MUCH (BERAPA) ==========
    def extract_how_much(self):
        """Extract HOW MUCH with FIXED patterns"""
        self.log("\n7️⃣ EXTRACTING HOW MUCH...")
        
        # Narcotics weight - improved
        weight_patterns = [
            r'(?:seberat|berat)\s+(\d+[,.]?\d*)\s+(?:\([^\)]+\)\s+)?gram',
            r'(\d+[,.]?\d*)\s+(?:\([^\)]+\)\s+)?gram',
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                weight_str = match.group(1).replace(',', '.')
                try:
                    weight = float(weight_str)
                    self._add_field("how_much", "narcotics_weight_grams", weight, 0.95)
                    self.log(f"  ✅ Narcotics Weight: {weight} grams")
                    break
                except ValueError:
                    continue
        
        # Prison sentence - improved
        prison_patterns = [
            r'pidana\s+penjara\s+selama\s+(\d+)\s+\([^\)]+\)\s+tahun(?:\s+dan\s+(\d+)\s+\([^\)]+\)\s+bulan)?',
            r'penjara\s+selama\s+(\d+)\s+tahun',
            r'dipidana\s+penjara\s+(\d+)\s+tahun'
        ]
        
        for pattern in prison_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                years = int(match.group(1))
                months = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
                
                sentence = {"years": years, "months": months}
                self._add_field("how_much", "prison_sentence", sentence, 0.95)
                self.log(f"  ✅ Prison: {years} years" + (f" {months} months" if months else ""))
                break
        
        # Fine - improved to get actual fine (not court fees)
        fine_pattern = r'denda\s+(?:sejumlah|sebesar)?\s*Rp\s*(\d+(?:\.\d{3})*(?:,\d+)?)'
        all_fines = []
        
        for match in re.finditer(fine_pattern, self.text, re.IGNORECASE):
            fine_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                fine_val = int(float(fine_str))
                all_fines.append(fine_val)
            except ValueError:
                continue
        
        if all_fines:
            # Get the largest fine (actual fine, not court fees)
            max_fine = max(all_fines)
            self._add_field("how_much", "fine_idr", max_fine, 0.95)
            self.log(f"  ✅ Fine: Rp {max_fine:,}")
        
        # FIXED: Subsidiary - more flexible pattern
        subsidiary_patterns = [
            r'subsidair\s+(\d+)\s+\([^\)]+\)\s+bulan',
            r'subsidair\s+(\d+)\s+bulan',
            r'subsider\s+(\d+)\s+bulan'
        ]
        
        for pattern in subsidiary_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                months = int(match.group(1))
                self._add_field("how_much", "subsidiary_months", months, 0.9)
                self.log(f"  ✅ Subsidiary: {months} months")
                break
        else:
            self.log("  ⚠️ Subsidiary: Not found")
        
        # FIXED: Court fees - better detection
        court_fee_patterns = [
            r'biaya\s+perkara\s+(?:sejumlah|sebesar)?\s*Rp\s*(\d+(?:\.\d{3})*)',
            r'membebankan.*?biaya.*?Rp\s*(\d+(?:\.\d{3})*)'
        ]
        
        for pattern in court_fee_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                fee_str = match.group(1).replace('.', '')
                try:
                    fee = int(fee_str)
                    self._add_field("how_much", "court_fees_idr", fee, 0.9)
                    self.log(f"  ✅ Court Fees: Rp {fee:,}")
                    break
                except ValueError:
                    continue
        
        # Evidence items - improved extraction
        evidence_items = []
        
        # Pattern for items with quantity
        item_patterns = [
            r'(\d+)\s+\([^\)]+\)\s+(unit|paket|bungkus|buah|lembar)\s+([^;\.]+)',
            r'(\d+)\s+(unit|paket|bungkus|buah|lembar)\s+([^;\.]+)'
        ]
        
        for pattern in item_patterns:
            for match in re.finditer(pattern, self.text, re.IGNORECASE):
                item = {
                    "quantity": int(match.group(1)),
                    "unit": match.group(2).lower(),
                    "description": match.group(3).strip()[:100]
                }
                evidence_items.append(item)
        
        if evidence_items:
            self._add_field("how_much", "evidence_items", evidence_items[:10], 0.85)
            self.log(f"  ✅ Evidence Items: {len(evidence_items)} items")
    
    def extract_all(self) -> Dict:
        """Extract all categories and return complete data"""
        self.log("="*60)
        self.log("STARTING IMPROVED EXTRACTION (v2.0)")
        self.log("="*60)
        
        self.extract_what()
        self.extract_when()
        self.extract_where()
        self.extract_who()
        self.extract_why()
        self.extract_how()
        self.extract_how_much()
        
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
        input_file = "../Cleaned-Doc/putusan_1678.txt"
        output_file = "../extract_result_1678_2.json"
    
    print(f"📄 Input: {input_file}")
    print(f"💾 Output: {output_file}\n")
    
    data, report = test_extractor(input_file, output_file)
    
    print(f"\n✅ Extraction complete! Check {output_file}")
