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
            "when": {},
            "where": {},
            "who": {},
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
                r'Pasal\s+[0-9A-Za-z\. ]+(?:\s+Jo\.?\s+Pasal\s+[0-9A-Za-z\. ]+)?(?=\n|;|,|\.)',
                window,
                re.IGNORECASE
            )
            
            if pasal_match:
                proven = pasal_match.group(0).strip()
                self._add_field("what", "proven_offence", proven, 0.97)
                self.log(f"  ✅ Proven Offence: {proven}")
                break

        # verdict per charge
        verdict_patterns = [
            (r'terbukti\s+(?:secara\s+)?(?:sah\s+dan\s+)?(?:meyakinkan\s+)?bersalah', "Bersalah", 0.98),
            (r'tidak\s+terbukti', "Tidak Terbukti", 0.98),
            (r'lepas\s+dari\s+segala\s+tuntutan', "Lepas", 0.98),
            (r'bebas', "Bebas", 0.95)
        ]

        for pattern, verdict, conf in verdict_patterns:
            if re.search(pattern, self.text, re.IGNORECASE):
                self._add_field("what", "verdict_per_charge", verdict, conf)
                self.log(f" ✅ Verdict: {verdict}")
                break
        
        # prison term
        prison_patterns = [
            r'pidana\s+penjara\s+selama\s+(\d+)\s+\([^\)]+\)\s+tahun(?:\s+dan\s+(\d+)\s+\([^\)]+\)\s+bulan)?',
            r'penjara\s+selama\s+(\d+)\s+tahun',
            r'dipidana\s+penjara\s+(\d+)\s+tahun'
        ]

        for pattern in prison_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                years = int(match.group(1))
                months = int(match.group(2)) if len(match.group()) > 1 and match.group(2) else 0

                sentence = {"years": years, "months": months}
                self._add_field("what", "prison_term", sentence, 0.95)
                self.log(f" ✅ Prison Term: {years} years" + (f" {months} months" if months else ""))
                break

        # detention credit
        for match in re.finditer(r'penangkapan|penahanan', self.text, re.IGNORECASE):
            start = max(0, match.start() - 200)
            end = match.end() + 300
            window = self.text[start:end].lower()

            if re.search(r'dikurangkan|diperhitungkan', window):
                self._add_field("what", "detention_credit", True, 0.97)
                self.log(" ✅ Detention Credit: applied")
                break

        # evidence items
        evidence_items = []
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
            self._add_field("what", "evidence_items", evidence_items[:10], 0.85)
            self.log(f" ✅ Evidence Items: {len(evidence_items)} items found")

        # evidence disposition
        evidence_disposition = []
        disposition_pattern = [
            r'(\d+\s*\([^)]+\)\s*\w+\s+[^\.]+)\.\s*(?:Barang\s+Bukti\s+)?(dikembalikan|dirampas|dimusnahkan)',
        ]

        for pattern in disposition_pattern:
            for match in re.finditer(pattern, self.text, re.IGNORECASE):
                item = match.group(1).strip()
                disposition = match.group(2).lower()

                evidence_disposition.append({
                    "unit": item,
                    "disposition": disposition
                })

            if evidence_disposition:
                self._add_field("what", "evidence_disposition", evidence_disposition, 0.95)
                self.log(f"  ✅ Evidence Disposition: {len(evidence_disposition)} items found")

        
        # defense plea
        plea_pattern = r'(pembelaan|pleidoi|nota\s+pembelaan).*?(?=menimbang)'
        plea_section = re.search(plea_pattern, self.text, re.IGNORECASE | re.DOTALL)

        if plea_section:
            section = plea_section.group(0).lower()

            if re.search(r'mohon.*?bebas', section):
                value = "bebas"
            elif re.search(r'mohon.*?lepas', section):
                value = "lepas"
            elif re.search(r'mohon.*?(keringanan|ringan)', section):
                value = "ringankan"
            else:
                value = "unknown"

            self._add_field("what", "defense_plea", value, 0.9)
            self.log(f"  ✅ Defense Plea: {value}")

        # aggravating and mitigating factors
        aggravating_match = re.search(
            r'keadaan\s+yang\s+memberatkan\s*:?\s*(.*?)(?=keadaan\s+yang\s+meringankan)',
            self.text,
            re.IGNORECASE | re.DOTALL
        )

        aggravating = []

        if aggravating_match:
            block = aggravating_match.group(1)
            aggravating = re.findall(r'-\s*(.*?)(?=\n\s*-|\Z)', block, re.DOTALL)
            aggravating = [
                re.sub(r'\s*\n\s*', ' ', item).strip()
                for item in aggravating if item.strip()
            ]

            self._add_field("what", "aggravating_factors", aggravating, 0.95)
            self.log(f"  ✅ Aggravating: {aggravating}")

        mitigating_match = re.search(
            r'keadaan\s+yang\s+meringankan\s*:?\s*(.*?)(?=\bMenimbang\b|\bMemperhatikan\b|\bMengingat\b)',
            self.text,
            re.IGNORECASE | re.DOTALL
        )

        if mitigating_match:
            block = mitigating_match.group(1)
            
            # Split per baris, bersihkan tiap item
            mitigating = [
                re.sub(r'\s+', ' ', item).strip().rstrip(';')
                for item in block.split('\n')
                if item.strip()
            ]

        self._add_field("what", "mitigating_factors", mitigating, 0.95)

        # related entities
        entities_pattern = [
            r'(?:jaringan|kelompok|organisasi|anggota)\s+(?:dari\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})'
        ]

        blacklist = {
            "Teroris",
            "Terdakwa",
            "Pemerintah",
            "Negara",
            "Indonesia"
        }

        found = set()

        for pattern in entities_pattern:
            for match in re.finditer(pattern, self.text):
                candidate = match.group(1).strip()

                if len(candidate.split()) > 4:
                    continue

                candidate = candidate.replace("\n", " ")

                if candidate in blacklist:
                    continue

            found.add(candidate)
        
        if found:
            self._add_field("what", "related_entities", list(found), 0.9)
            self.log(f"✅ Related Entities: {len(found)} items found")
        
        # appellate outcome
        outcome_value = []

        amar_match = re.search(
            r'(M\s*E\s*N\s*G\s*A\s*D\s*I\s*L\s*I|AMAR\s+PUTUSAN)(.*?)(?=Demikian|Ditetapkan|$)',
            self.text,
            re.IGNORECASE | re.DOTALL
        )

        amar_block = amar_match.group(2) if amar_match else ""

        outcome_match = re.search(
            r'\b(menguatkan|mengubah|membatalkan)\b',
            amar_block,
            re.IGNORECASE
        )

        if outcome_match:
            outcome_value = [outcome_match.group(1).lower()]

        self._add_field("what", "appellate_outcome", outcome_value, 0.95)
        self.log(f"✅ Appellate Outcome: {outcome_value}")

        # defendant passport
        passport_match = re.search(
            r'(?:Nomor\s+)?Paspor\s*[:\-]?\s*([A-Z]\d{6,8})',
            self.text,
            re.IGNORECASE
        )

        passport = passport_match.group(1) if passport_match else None
        self._add_field("what", "defendant_passport_no", passport, 0.9)

        # defendant nik
        nik_match = re.search(
            r'NIK\s*[:\-]?\s*(\d{16})',
            self.text,
            re.IGNORECASE
        )
        nik = nik_match.group(1) if nik_match else None
        self._add_field("what", "defendant_nik", nik, 0.9)

        # defendant kk
        kk_match = re.search(
            r'(?:Nomor\s+)?(?:Kartu\s+Keluarga|KK)\s*[:\-]?\s*(\d{16})',
            self.text,
            re.IGNORECASE
        )
        kk = kk_match.group(1) if kk_match else None
        self._add_field("what", "defendant_kk_no", kk, 0.9)

        # defendant education
        education_match = re.search(
            r'Pendidikan\s*\n?\s*([^\n]+)',
            self.text,
            re.IGNORECASE
        )
        education = education_match.group(1).strip() if education_match else None
        self._add_field("what", "defendant_education_status", education, 0.85)

        # chat platform
        platform_contexts = re.findall(
            r'(?:aplikasi|media sosial|platform|pesan|chat|komunikasi|grup|channel|akun|bergabung|berbaiat|mengirim|menerima)'
            r'.{0,100}'
            r'\b(Telegram|WhatsApp|Facebook|Instagram|Twitter|YouTube|Signal|'
            r'Zello|Discord|Line|WeChat|Messenger|Skype|TikTok)\b'
            r'|\b(Telegram|WhatsApp|Facebook|Instagram|Twitter|YouTube|Signal|'
            r'Zello|Discord|Line|WeChat|Messenger|Skype|TikTok)\b'
            r'.{0,100}'
            r'(?:aplikasi|grup|channel|akun|pesan|chat|komunikasi|bergabung|mengirim|menerima)',
            self.text,
            re.IGNORECASE | re.DOTALL
        )

        # Flatten tuple results, deduplikasi
        platforms_found = list(dict.fromkeys(
            p.strip().capitalize()
            for group in platform_contexts
            for p in group
            if p.strip()
        ))

        platform = platforms_found if platforms_found else None
        self._add_field("what", "defendant_chat_platform", platform, 0.8)

        # Gender
        gender_match = re.search(
            r'Jenis\s+Kelamin\s*[:\-]?\s*(Laki[\s\-]+laki|Perempuan|Wanita|Pria)',
            self.text,
            re.IGNORECASE
        )
        gender_raw = gender_match.group(1).strip() if gender_match else None
        # Normalize
        if gender_raw:
            gender = "Laki-laki" if re.search(r'laki|pria', gender_raw, re.IGNORECASE) else "Perempuan"
        else:
            gender = None
        self._add_field("what", "defendant_gender", gender, 0.95)

        # Nationality
        nationality_match = re.search(
            r'Kebangsaan\s*[:\-]?\s*([^\n]+)',
            self.text,
            re.IGNORECASE
        )
        nationality = nationality_match.group(1).strip() if nationality_match else None
        self._add_field("what", "defendant_nationality", nationality, 0.9)

        # Religion
        religion_match = re.search(
            r'Agama\s*[:\-]?\s*(Islam|Kristen|Katolik|Hindu|Buddha|Konghucu|[^\n]+)',
            self.text,
            re.IGNORECASE
        )
        religion = religion_match.group(1).strip() if religion_match else None
        self._add_field("what", "defendant_religion", religion, 0.9)

        # Occupation
        occupation_match = re.search(
            r'Pekerjaan\s*[:\-]?\s*([^\n]+?)(?:\s+Pendidikan|\n|$)',
            self.text,
            re.IGNORECASE
        )
        occupation = occupation_match.group(1).strip() if occupation_match else None
        self._add_field("what", "defendant_occupation", occupation, 0.85)

        # Ideology Affiliation
        ideology_keywords = re.search(
            r'\b(ISIS|ISIL|Al[\s\-]?Qaeda|JAD|JI|MIT|Mujahidin\s+Indonesia\s+Timur|'
            r'Anshor\s+Daulah|Jemaah\s+Islamiyah|Katibah\s+Nusantara|'
            r'HTI|Taliban|NII|DI\/TII|Darul\s+Islam|MMI)\b',
            self.text,
            re.IGNORECASE
        )
        ideology = ideology_keywords.group(1).strip() if ideology_keywords else None
        self._add_field("what", "defendant_ideology_affiliation", ideology, 0.7)

        # Local Network
        network_match = re.search(
            r'\b(ISIS|ISIL|Al[\s\-]?Qaeda|JAD|JI|MIT|Mujahidin\s+Indonesia\s+Timur|'
            r'Anshor\s+Daulah|Jemaah\s+Islamiyah|Katibah\s+Nusantara|'
            r'HTI|Taliban|NII|DI\/TII|Darul\s+Islam|MMI)'
            r'(?:\s+([A-Z][a-z]+)){0,2}', 
            self.text
        )
        if network_match:
            network = network_match.group(0).strip()
            network = re.split(
                r'\s+(?:pimpinan|yang|dan|atau|kemudian|oleh|di\b|ke\b|dari|cabang|wilayah)\b',
                network,
                flags=re.IGNORECASE
            )[0].strip()
        else:
            network = None
        self._add_field("what", "defendant_local_network", network, 0.7)

        # has attack plan
        attack_plan_keywords = re.search(
            r'(?:rencana|merencanakan|berencana|mempersiapkan|menyiapkan)'
            r'.{0,80}'
            r'(?:amaliyah|penyerangan|serangan|bom|jihad|operasi|aksi|target|sasaran)',
            self.text,
            re.IGNORECASE | re.DOTALL
        )

        has_attack_plan = bool(attack_plan_keywords)
        self._add_field("what", "has_attack_plan", has_attack_plan, 0.85)

        # attack preparation
        prep_keywords = re.search(
            r'\b(idad|i\'dad|survei|survey|pembagian\s+tugas|escape|bekal\s+perjalanan|'
            r'latihan|melatih|pengadaan|membeli|mempersiapkan|menyiapkan|koordinasi|'
            r'pertemuan|rapat|rekrutmen|perekrutan|uji\s+coba|observasi|pengintaian)\b',
            self.text,
            re.IGNORECASE
        )

        if prep_keywords:
            sentences = re.split(r'(?<=[.;])\s+', self.text)
            prep_activities = [
                s.strip() for s in sentences
                if re.search(
                    r'\b(idad|i\'dad|survei|survey|pembagian\s+tugas|escape|bekal|'
                    r'latihan|pengadaan|membeli|mempersiapkan|koordinasi|'
                    r'pertemuan|rapat|rekrutmen|uji\s+coba|observasi|pengintaian)\b',
                    s, re.IGNORECASE
                )
            ]
        else:
            prep_activities = None
        self._add_field("what", "attack_preparation_activities", prep_activities, 0.75)

        # attack plan summary
        plan_keywords = re.search(
            r'\b(membunuh|mengeksekusi|eksekutor|meledakkan|menembak|menyerang|'
            r'golok|senjata|bom|target|sasaran|korban|waktu\s+pelaksanaan|'
            r'lokasi\s+(?:serangan|penyerangan)|peran\s+(?:pelaku|terdakwa))\b',
            self.text,
            re.IGNORECASE
        )

        if plan_keywords:
            sentences = re.split(r'(?<=[.;])\s+', self.text)
            plan_sentences = [
                s.strip() for s in sentences
                if re.search(
                    r'\b(membunuh|mengeksekusi|eksekutor|meledakkan|menembak|menyerang|'
                    r'golok|senjata|bom|target|sasaran|korban|waktu\s+pelaksanaan|'
                    r'lokasi\s+(?:serangan|penyerangan))\b',
                    s, re.IGNORECASE
                )
            ]
            attack_plan_summary = " | ".join(plan_sentences[:3]) if plan_sentences else None
        else:
            attack_plan_summary = None
        self._add_field("what", "attack_plan_summary", attack_plan_summary, 0.75)


        # radicalization sources
        rad_sources = []

        books_raw = re.findall(
            r'berjudul\s+["\u201c]?([^""\u201d;\n]{5,60})["\u201d]?',
            self.text, re.IGNORECASE
        )

        seen_keys = set()
        books_deduped = []
        for b in books_raw:
            title = b.strip().rstrip(',.')
            key = ' '.join(title.lower().split()[:4])
            if key not in seen_keys:
                seen_keys.add(key)
                books_deduped.append(f"buku/majalah: {title}")

        if books_deduped:
            rad_sources.extend(books_deduped)

        if re.search(r'\b(pengajian|kajian|halaqah|daurah|talim)\b', self.text, re.IGNORECASE):
            rad_sources.append("kajian/pengajian")

        mentor = re.findall(
            r'(?:diajarkan|direkrut|dibai[ao]t|dipengaruhi|berguru|belajar)\s+(?:oleh|kepada|dari)\s+'
            r'([A-Z][a-z]+(?:\s+(?:alias|bin|binti|[A-Z][a-z]+)){0,4})',
            self.text, re.IGNORECASE
        )
        if mentor:
            rad_sources.extend([f"tokoh/mentor: {m.strip()}" for m in dict.fromkeys(mentor)])

        media = re.findall(
            r'(?:melalui|dari|lewat|mengakses|menonton|membaca)\s+'
            r'(?:kanal|channel|grup|akun|situs|website|konten)?\s*'
            r'(Telegram|WhatsApp|YouTube|Facebook|Instagram|Twitter|Signal|Zello)',
            self.text, re.IGNORECASE
        )
        if media:
            rad_sources.extend([f"platform: {m.strip()}" for m in dict.fromkeys(media)])

        bai = re.search(
            r'(?:wajib\s+)?berbaiat|baiat\s+kepada\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
            self.text, re.IGNORECASE
        )
        if bai:
            rad_sources.append(f"bai'at: {bai.group(1).strip()}" if bai.lastindex and bai.group(1) else "bai'at")

        radicalization_sources = list(dict.fromkeys(rad_sources)) if rad_sources else None
        self._add_field("what", "radicalization_sources", radicalization_sources, 0.7)

    # ======= WHERE ========

    def extract_where(self):
        """Extract WHERE - locations, court, arrest, detention, defendant address"""
        self.log("\n3️⃣ EXTRACTING WHERE...")

        # COURT LOCATION
        court_location_patterns = [
            r'Pengadilan\s+Negeri\s+([A-Za-z\s]+?)(?:\s+Yang\s+Mengadili|\s+Nomor|\s+tanggal|\s+Kelas)',
            r'Pengadilan\s+Negeri\s+([A-Za-z\s]+?)(?=\s*\n)',
        ]
        for pattern in court_location_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                court_location = match.group(1).strip()
                self._add_field("where", "court_location", court_location, 0.95)
                self.log(f"  ✅ Court Location: {court_location}")
                break

        # Courts
        court_patterns = {
            'district_court': r'Pengadilan\s+Negeri\s+([A-Za-z\s]+?)(?:\s+Nomor|\s+tanggal|\s+Kelas|\s+Yang)',
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

        # CRIME LOCATIONS (multi-lokasi)

        crime_loc_match = re.search(
            r'(?:bertempat|dilakukan|terjadi|berlokasi)\s+di\s+(.+?)'
            r'(?=\s*(?:pada|sekitar\s+pukul|Menimbang|bahwa\s+terdakwa|;|\n\n))',
            self.text, re.IGNORECASE | re.DOTALL
        )
        if crime_loc_match:
            raw = crime_loc_match.group(1).strip()

            locations = re.split(r'\s+(?:atau|dan)\s+(?:di\s+)?(?=\w)', raw, flags=re.IGNORECASE)
            crime_locations = [' '.join(loc.split()).rstrip(',;') for loc in locations if loc.strip()]
            self._add_field("where", "crime_locations", crime_locations, 0.85)
            self.log(f"  ✅ Crime Locations: {crime_locations}")

        # ARREST LOCATION
        arrest_patterns = [
            r'(?:ditangkap|penangkapan)\s+(?:di|pada)\s+'
            r'((?:Jln?\.?|Jalan|Desa|Kelurahan|Kecamatan|Kota|Kabupaten|'
            r'Komplek|Perumahan|Rutan|Bandara|Pasar|Masjid|Kantor)'
            r'[^;.\n]{5,80})',
            r'tempat\s+penangkapan\s*[:\-]?\s*'
            r'((?:Jln?\.?|Jalan|Desa|Kelurahan|Kecamatan|Kota|Kabupaten)'
            r'[^;.\n]{5,80})',
        ]
        for pattern in arrest_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                arrest_location = ' '.join(match.group(1).split()).rstrip(',;')
                self._add_field("where", "arrest_location", arrest_location, 0.85)
                self.log(f"  ✅ Arrest Location: {arrest_location}")
                break
        else:
            self.log("  ⚠️ Arrest Location: tidak ditemukan")

        # DETENTION LOCATION
        detention_patterns = [
            r'Rumah\s+Tahanan\s+Negara\s+(?:Kelas\s+[\w]+\s+)?([A-Za-z\s]+?)(?:\s+oleh|\s*;|\s*\n)',
            r'(?:ditahan|penahanan)\s+(?:di|pada)\s+(Rutan|Lapas|Rumah\s+Tahanan)[^;.\n]*',
            r'(Rutan|Lapas)\s+([A-Za-z\s]+?)(?:\s+oleh|\s*;|\s*\n)',
        ]
        for pattern in detention_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                detention = ' '.join(match.group(0).split()).rstrip(',;')
                self._add_field("where", "detention_location", detention, 0.85)
                self.log(f"  ✅ Detention Location: {detention}")
                break

        # DEFENDANT ADDRESS
        address_patterns = [
            r'Tempat\s+Tinggal\s*[:\-]?\s*([^;]+?)(?=Agama|Pekerjaan|Pendidikan|\n\n)',
            r'Alamat\s*[:\-]?\s*([^;]+?)(?=Agama|Pekerjaan|Pendidikan|\n\n)',
            r'beralamat\s+di\s+([^;]+?)(?=Agama|Pekerjaan|;)',
            r'bertempat\s+tinggal\s+di\s+([^;]+?)(?=Agama|Pekerjaan|;)',
        ]
        for pattern in address_patterns:
            match = re.search(pattern, self.text, re.DOTALL | re.IGNORECASE)
            if match:
                address = ' '.join(match.group(1).split()).strip()
                self._add_field("where", "defendant_address", address, 0.95)
                self.log(f"  ✅ Defendant Address: {address[:80]}...")
                break

        # DEFENDANT PLACE OF BIRTH
        pob_patterns = [
            r'Tempat\s+(?:Lahir|/\s*Tanggal\s+Lahir)\s*[:\-]?\s*([A-Za-z\s]+?)(?=\s*(?:Umur|Tanggal|\d|,|\n))',
            r'lahir\s+di\s+([A-Za-z\s]+?)(?=\s*(?:pada|,|\d|\n))',
        ]
        for pattern in pob_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                pob = match.group(1).strip()
                self._add_field("where", "defendant_pob", pob, 0.9)
                self.log(f"  ✅ Place of Birth: {pob}")
                break

        # ACTIVITY LOCATIONS (latihan, pertemuan, dll)
        activity_loc_keywords = re.findall(
            r'(?:latihan|pelatihan|pertemuan|rapat|villa|pesantren|yayasan|markas|camp|training)'
            r'[^.;]{0,30}'
            r'(?:di|berlokasi\s+di|bertempat\s+di)\s+'
            r'([A-Za-z][^.;\n]{5,60})',
            self.text, re.IGNORECASE
        )
        if activity_loc_keywords:
            activity_locations = list(dict.fromkeys(
                ' '.join(loc.split()).rstrip(',;')
                for loc in activity_loc_keywords
            ))
            self._add_field("where", "activity_locations", activity_locations, 0.75)
            self.log(f"  ✅ Activity Locations: {activity_locations}")

    # ============ WHERE ===============

    def extract_when(self):
        """Extract WHEN - dates, timelines, ranges"""
        self.log("\n2️⃣ EXTRACTING WHEN...")

        # Indonesian months mapping
        months = {
            'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
            'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
        }

        date_pattern = r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})'
        year_pattern = r'\b(19|20)\d{2}\b'

        # Extract all dates with context
        dates_with_context = []
        for match in re.finditer(date_pattern, self.text, re.IGNORECASE):
            start = max(0, match.start() - 150)
            context = self.text[start:match.start()].lower()
            dates_with_context.append({
                'date': match.group(0),
                'context': context,
                'position': match.start()
            })

        self.log(f"  ✅ Found {len(dates_with_context)} dates")

        # DEFENDANT DOB
        for item in dates_with_context:
            if re.search(r'(?:lahir|tanggal\s+lahir|umur)', item['context']):
                self._add_field("when", "defendant_dob", item['date'], 0.95)
                self.log(f"  ✅ DOB: {item['date']}")
                break

        # ARREST DATE
        for item in dates_with_context:
            if re.search(r'(?:ditangkap|penangkapan|sejak\s+ditangkap)', item['context']):
                self._add_field("when", "arrest_date", item['date'], 0.9)
                self.log(f"  ✅ Arrest Date: {item['date']}")
                break

        # INDICTMENT DATE
        for item in dates_with_context:
            if re.search(r'(?:surat\s+dakwaan|dakwaan\s+tanggal|didakwa)', item['context']):
                self._add_field("when", "indictment_date", item['date'], 0.9)
                self.log(f"  ✅ Indictment Date: {item['date']}")
                break

        # CRIME TIME RANGE
        crime_range_match = re.search(
            r'(?:melakukan|melaksanakan|terjadi|perbuatan|kejadian)'
            r'[^.;]{0,50}'
            r'(?:antara|sekitar|pada|sejak)\s+'
            r'((?:bulan\s+|tahun\s+)?\w+[\w\s,]+?)'
            r'\s+(?:sampai\s+dengan|hingga|s/d)\s+'
            r'((?:bulan\s+|tahun\s+)?[\w\s,]+?)'
            r'(?=\s*,|\s*bertempat|\s*di\s+|\s*\n)',
            self.text, re.IGNORECASE | re.DOTALL
        )

        if not crime_range_match:
            # Fallback: year range dengan konteks tindak pidana
            crime_range_match = re.search(
                r'(?:antara|sekitar|sejak)\s+tahun\s+(\d{4})\s+'
                r'(?:sampai\s+dengan|hingga|s/d)\s+(?:tahun\s+)?(\d{4})'
                r'(?=[^.;]{0,80}(?:bertempat|melakukan|tindak\s+pidana))',
                self.text, re.IGNORECASE
            )
            if crime_range_match:
                crime_time_range = f"antara tahun {crime_range_match.group(1)} sampai dengan tahun {crime_range_match.group(2)}"
                self._add_field("when", "crime_time_range", crime_time_range, 0.85)
                self.log(f"  ✅ Crime Time Range: {crime_time_range}")
        else:
            start_time = ' '.join(crime_range_match.group(1).split())
            end_time = ' '.join(crime_range_match.group(2).split())
            crime_time_range = f"{start_time} sampai dengan {end_time}"
            self._add_field("when", "crime_time_range", crime_time_range, 0.85)
            self.log(f"  ✅ Crime Time Range: {crime_time_range}")

        # DETENTION TIMELINE
        detention_keywords = r'(?:ditahan|penahanan|perpanjangan\s+penahanan|ditahan\s+oleh)'
        detention_entries = []
        for match in re.finditer(date_pattern, self.text, re.IGNORECASE):
            start = max(0, match.start() - 200)
            context = self.text[start:match.start()].lower()
            if re.search(detention_keywords, context):
                # Ambil konteks singkat sebagai label
                label_match = re.search(
                    r'(penyidik|penuntut\s+umum|JPU|hakim|pengadilan\s+negeri|'
                    r'pengadilan\s+tinggi|perpanjangan(?:\s+pertama|\s+kedua|\s+ketiga)?)',
                    context, re.IGNORECASE
                )
                label = label_match.group(1).strip() if label_match else "penahanan"
                detention_entries.append(f"{label}: {match.group(0)}")

        if detention_entries:
            # Deduplikasi
            detention_timeline = list(dict.fromkeys(detention_entries))
            self._add_field("when", "detention_timeline", detention_timeline, 0.85)
            self.log(f"  ✅ Detention Timeline: {detention_timeline}")

        # APPEAL TIMELINE
        appeal_keywords = r'(?:banding|kasasi|peninjauan\s+kembali|PK)'
        appeal_entries = []
        for match in re.finditer(date_pattern, self.text, re.IGNORECASE):
            start = max(0, match.start() - 200)
            context = self.text[start:match.start()].lower()
            if re.search(appeal_keywords, context):
                label_match = re.search(
                    r'(permintaan\s+banding|putusan\s+banding|kasasi|'
                    r'peninjauan\s+kembali|PK|pengajuan)',
                    context, re.IGNORECASE
                )
                label = label_match.group(1).strip() if label_match else "banding"
                appeal_entries.append(f"{label}: {match.group(0)}")

        if appeal_entries:
            appeal_timeline = list(dict.fromkeys(appeal_entries))
            self._add_field("when", "appeal_timeline", appeal_timeline, 0.85)
            self.log(f"  ✅ Appeal Timeline: {appeal_timeline}")

        # DEFENDANT LOCAL NETWORK JOINED AT
        joined_match = re.search(
            r'(?:bergabung|masuk|berbaiat|direkrut|menjadi\s+anggota)'
            r'[^.;]{0,80}'
            r'(?:pada\s+(?:tahun\s+)?|tahun\s+)(\d{4})'
            r'|'
            r'(?:pada\s+(?:tahun\s+)?|sejak\s+(?:tahun\s+)?)(\d{4})'
            r'[^.;]{0,80}'
            r'(?:bergabung|masuk|berbaiat|direkrut|menjadi\s+anggota)',
            self.text, re.IGNORECASE
        )
        if joined_match:
            year = joined_match.group(1) or joined_match.group(2)
            self._add_field("when", "defendant_local_network_joined_at", year, 0.75)
            self.log(f"  ✅ Network Joined At: {year}")

        # COURT DATES
        for item in dates_with_context:
            if re.search(r'pengadilan\s+negeri', item['context']):
                self._add_field("when", "district_court_date", item['date'], 0.9)
                self.log(f"  ✅ District Court Date: {item['date']}")
                break

        for item in dates_with_context:
            if re.search(r'pengadilan\s+tinggi', item['context']):
                self._add_field("when", "high_court_date", item['date'], 0.9)
                self.log(f"  ✅ High Court Date: {item['date']}")
                break

        # Store all dates for reference
        all_dates = [item['date'] for item in dates_with_context[:15]]
        self._add_field("when", "all_dates", all_dates, 0.95)

    # =========== WHO =============
    def extract_who(self):
        """Extract WHO - defendants, judges, clerks, prosecutors, defense, investigators, witnesses, co-defendants"""
        self.log("\n4️⃣ EXTRACTING WHO...")

        # DEFENDANT NAMES (+ alias)
        name_patterns = [
            r'Nama\s+Lengkap\s*[:\-]?\s*([A-Z][A-Za-z\s\.]+?(?:\s+(?:alias|Als?|bin|binti)\s+[A-Z][A-Za-z\s\.]+)*?)(?=\s*(?:Tempat\s+Lahir|;|\n\n))',
            r'Nama\s*[:\-]?\s*([A-Z][A-Za-z\s\.]+?\s+(?:bin|binti)\s+[A-Z][A-Za-z\s\.]+)',
            r'Nama\s*[:\-]?\s*([A-Z][A-Z\s\.]+?)(?:\s*;|\s*Tempat)',
            r'Terdakwa\s+([A-Z][A-Za-z\s\.]+?\s+(?:bin|binti)\s+[A-Z][A-Za-z\s\.]+)'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                name = ' '.join(match.group(1).split())
                self._add_field("who", "defendant_names", name, 0.95)
                self.log(f"  ✅ Defendant Names: {name}")
                break
        else:
            self.log("  ❌ Defendant Names: NOT FOUND")

        # JUDGES
        # ============================================================
        judges = {}

        # Hakim Ketua
        ketua_match = re.search(
            r'oleh\s+Kami\s+([A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?|M\.?\s*H(?:um)?\.?)[A-Za-z\s\.,]*?)'
            r'\s+selaku\s+Hakim\s+Ketua',
            self.text, re.IGNORECASE
        )
        if ketua_match:
            judges['ketua'] = ' '.join(ketua_match.group(1).split()).rstrip(',')
            self.log(f"  ✅ Hakim Ketua: {judges['ketua']}")

        # Hakim Anggota - ambil nama sebelum "masing-masing sebagai Hakim Anggota"
        anggota_match = re.search(
            r'((?:[A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?|M\.?\s*H(?:um)?\.?)[A-Za-z\s\.,]*?)'
            r'(?:\s+dan\s+[A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?|M\.?\s*H(?:um)?\.?)[A-Za-z\s\.,]*?)?)'
            r'\s+masing-masing\s+sebagai\s+Hakim\s+Anggota',
            self.text, re.IGNORECASE
        )
        if anggota_match:
            raw = anggota_match.group(1)
            anggota_list = re.split(r'\s+dan\s+', raw)
            judges['anggota'] = [' '.join(a.split()).rstrip(',') for a in anggota_list if a.strip()]
            self.log(f"  ✅ Hakim Anggota: {judges['anggota']}")

        if judges:
            self._add_field("who", "judges", judges, 0.9)

        # ============================================================
        # CLERK (Panitera Pengganti)
        # ============================================================
        clerk_match = re.search(
            r'dibantu\s+oleh\s+([A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?|M\.?\s*H(?:um)?\.?)[A-Za-z\s\.,]*?)'
            r'\s+Panitera\s+Pengganti',
            self.text, re.IGNORECASE
        )
        if not clerk_match:
            # Fallback: ambil nama setelah "Panitera Pengganti," di blok tanda tangan
            clerk_match = re.search(
                r'Panitera\s+Pengganti\s*,\s*\n\s*([A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?))',
                self.text, re.IGNORECASE
            )
        if clerk_match:
            clerk = ' '.join(clerk_match.group(1).split()).rstrip(',.')
            self._add_field("who", "clerk", clerk, 0.9)
            self.log(f"  ✅ Clerk: {clerk}")

        # ============================================================
        # PROSECUTORS
        # ============================================================
        prosecutor_match = re.search(
            r'dihadiri\s+oleh\s+([A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?)?[A-Za-z\s\.,]*?)'
            r'\s+(?:selaku\s+)?Penuntut\s+Umum',
            self.text, re.IGNORECASE
        )
        if prosecutor_match:
            names_raw = prosecutor_match.group(1)
            names = re.split(r'\s*,\s*|\s+dan\s+', names_raw)
            prosecutors = {
                "names": [' '.join(n.split()).rstrip(',') for n in names if n.strip()],
                "office": None
            }
            # Cari office
            office_match = re.search(
                r'(?:Jaksa\s+Penuntut\s+Umum|Penuntut\s+Umum)\s+pada\s+(Kejaksaan[^,;\n]+)',
                self.text, re.IGNORECASE
            )
            if office_match:
                prosecutors["office"] = ' '.join(office_match.group(1).split())

            self._add_field("who", "prosecutors", prosecutors, 0.9)
            self.log(f"  ✅ Prosecutors: {prosecutors}")

        # DEFENSE COUNSELS
        defense_block = re.search(
            r'(?:Penasihat\s+Hukum|Kuasa\s+Hukum|Pengacara|Advokat)[^:]*?[:\-]?\s*'
            r'((?:[A-Z][A-Za-z\s\.,]+?(?:S\.?\s*H\.?)?'
            r'(?:\s*,\s*|\s+dan\s+))+[A-Z][A-Za-z\s\.,]+?)'
            r'(?=\s*(?:;|\n\n|dari\s+|berkantor))',
            self.text, re.IGNORECASE | re.DOTALL
        )
        if defense_block:
            raw = defense_block.group(1)
            counsels = re.split(r'\s*(?:,\s*|\s+dan\s+)(?=[A-Z])', raw)
            defense_counsels = [' '.join(c.split()).rstrip(',') for c in counsels if c.strip()]
            self._add_field("who", "defense_counsels", defense_counsels, 0.85)
            self.log(f"  ✅ Defense Counsels: {defense_counsels}")

        # INVESTIGATORS
        investigator_match = re.search(
            r'\b(Densus\s*88|Detasemen\s+Khusus\s+88|BNPT|Polri|Polda\s+[A-Za-z\s]+|'
            r'Polres\s+[A-Za-z\s]+|Bareskrim|Satgas\s+[A-Za-z\s]+)\b',
            self.text, re.IGNORECASE
        )
        if investigator_match:
            investigator = ' '.join(investigator_match.group(1).split())
            self._add_field("who", "investigators", investigator, 0.85)
            self.log(f"  ✅ Investigators: {investigator}")

        # WITNESSES
        witness_block = re.search(
            r'SAKSI\s+(?:BAGI\s+TERDAKWA|[A-Z]+)[:\s]*\n(.*?)(?=\n\n|\Z)',
            self.text, re.IGNORECASE | re.DOTALL
        )
        if witness_block:
            raw = witness_block.group(1)
            witnesses = re.findall(r'\d+\.\s*([A-Z][A-Za-z\s\.]+?)(?=\s*\d+\.|\s*;|\n\n|\Z)', raw)
            if witnesses:
                witnesses_clean = [' '.join(w.split()).rstrip(',;') for w in witnesses]
                self._add_field("who", "witnesses", witnesses_clean, 0.8)
                self.log(f"  ✅ Witnesses: {witnesses_clean}")

        # CO-DEFENDANTS
        co_defendant_matches = re.findall(
            r'(?:penuntutan\s+terpisah|berkas\s+terpisah)[^A-Z]*'
            r'([A-Z][A-Z\s]+(?:\s+[Aa]ls?\s+[A-Z][A-Za-z\s]+)*)',
            self.text, re.IGNORECASE
        )
        if co_defendant_matches:
            co_defendants = [' '.join(c.split()).rstrip(',;') for c in co_defendant_matches]
            self._add_field("who", "co_defendants", co_defendants, 0.8)
            self.log(f"  ✅ Co-Defendants: {co_defendants}")

        # EXISTING: Birth place, age, birth date, prosecutor office
        birth_patterns = [
            r'Tempat\s+Lahir\s*[:\-]?\s*([^;\n]+?)(?=Umur|Tanggal\s+Lahir|;|\n)',
            r'lahir\s+di\s+([A-Za-z\s]+?)(?:,|\s+pada)'
        ]
        for pattern in birth_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                birth_place = ' '.join(match.group(1).split())
                self._add_field("who", "birth_place", birth_place, 0.9)
                self.log(f"  ✅ Birth Place: {birth_place}")
                break

        age_match = re.search(
            r'(?:Umur[^:]*:\s*)?(\d+)\s+[Tt]ahun[/\s]+(\d{1,2}\s+\w+\s+\d{4})',
            self.text, re.IGNORECASE
        )
        if age_match:
            self._add_field("who", "age", int(age_match.group(1)), 0.98)
            self._add_field("who", "birth_date", age_match.group(2), 0.95)
            self.log(f"  ✅ Age: {age_match.group(1)}, DOB: {age_match.group(2)}")

    def extract_all(self) -> Dict:
        """Extract all categories and return complete data"""
        self.log("="*60)
        self.log("STARTING IMPROVED EXTRACTION (v2.0)")
        self.log("="*60)
        
        self.extract_what()
        self.extract_when()
        self.extract_where()
        self.extract_who()
        
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


        
