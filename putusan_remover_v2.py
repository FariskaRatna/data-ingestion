from PyPDF4 import PdfFileReader, PdfFileWriter
from PyPDF4.pdf import ContentStream
from PyPDF4.generic import TextStringObject, NameObject, ArrayObject
from PyPDF4.utils import b_
import PyPDF2
import fitz  # PyMuPDF
import os
import re
from pathlib import Path

# ============================================================
# Helper: normalisasi unicode / karakter aneh (text preprocessing)
# ============================================================
def normalize_unicode_artifacts(text: str) -> str:
    """
    Bersihkan karakter yang sering muncul dari hasil ekstraksi PDF putusan MA.
    """
    # Karakter yang sering nyelip
    text = text.replace("\ufeff", "")   # BOM
    text = text.replace("\ufffd", "")   # replacement char
    text = text.replace("\u00ad", "")   # soft hyphen

    # Bullet khas dari font PDF putusan: "" -> "•"
    text = text.replace("", "•")

    # Artefak "￾" yang sering muncul di tengah kata
    text = text.replace("￾", "")

    # Zero-width chars (sering bikin tokenisasi kacau)
    zero_width = [
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    ]
    for ch in zero_width:
        text = text.replace(ch, "")

    return text


def fix_spaced_letters(text: str, min_letters: int = 3) -> str:
    """
    Gabungkan huruf yang terpisah spasi:
      - "N a m a" -> "Nama"
      - "P U T U S A N" -> "PUTUSAN"

    Aman untuk singkatan 2 huruf seperti "P T" (tidak digabung karena min_letters=3).
    """
    spaced_re = re.compile(r"\b(?:[A-Za-z]\s){2,}[A-Za-z]\b")

    def repl(m: re.Match) -> str:
        tok = m.group(0)
        letters = tok.split()
        if len(letters) < min_letters:
            return tok

        joined = "".join(letters)

        # Kalau seluruhnya huruf kapital -> biarkan uppercase
        if joined.isupper():
            return joined

        # Kalau pola Title-ish, misal "N a m a" -> "Nama"
        return joined[0].upper() + joined[1:]

    return spaced_re.sub(repl, text)


def merge_label_colon_lines(text: str) -> str:
    """
    Kalau ada format:
      Nama
      : Budi
    -> jadi:
      Nama : Budi

    Berguna untuk PDF yang layout-nya memecah label dan value ke baris berikutnya.
    """
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i].rstrip()
        nxt = lines[i + 1].lstrip() if i + 1 < len(lines) else None

        cur_strip = cur.strip()
        if nxt is not None:
            if cur_strip and ":" not in cur_strip and nxt.startswith(":"):
                out.append(f"{cur_strip} {nxt.strip()}")
                i += 2
                continue

            if cur_strip.endswith(":") and nxt and not nxt.startswith(":"):
                out.append(f"{cur_strip} {nxt.strip()}")
                i += 2
                continue

        out.append(cur)
        i += 1

    return "\n".join(out)

def fix_glued_words(text: str) -> str:
    """
    Perbaiki kata yang nempel akibat ekstraksi PDF.
    Dibuat konservatif (lebih aman daripada terlalu agresif).
    """

    # A) ALLCAPS nempel ke kata kecil: "PATRASmenghubungi" -> "PATRAS menghubungi"
    text = re.sub(r"([A-Z]{2,})([a-z])", r"\1 \2", text)

    # B) kata kecil nempel ke ALLCAPS: "denganMUHAMMAD" -> "dengan MUHAMMAD"
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # C) "...alias" nempel: "ROSYIDalias" -> "ROSYID alias"
    text = re.sub(r"(?i)([A-Za-z])(?=alias\b)", r"\1 ", text)

    # D) Partikel/preposisi yang nempel ke token ALLCAPS:
    #    "SAYURke" -> "SAYUR ke" (di data kamu ada "YONO SAYURke Poso")
    particles = r"(ke|di|dari|dan|yang|pada|untuk|dengan|kepada|sebagai)"
    text = re.sub(rf"([A-Z]{{2,}})({particles})\b", r"\1 \2", text, flags=re.IGNORECASE)

    return text


def merge_allcaps_lines(text: str) -> str:
    """
    Gabungkan baris 'nama' ALLCAPS yang terpecah karena line-break PDF.
    Contoh: baris "BENHARD" lalu baris "ONASIS" lalu baris "PATRAS ..." -> digabung.
    """
    lines = text.splitlines()
    out = []
    i = 0

    def is_allcaps_line(s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        # hanya huruf/spasi/titik/koma/strip
        if not re.match(r"^[A-Z .,/-]+$", s):
            return False
        # minimal ada 1 huruf
        return any("A" <= ch <= "Z" for ch in s)

    while i < len(lines):
        cur = lines[i].rstrip()
        if is_allcaps_line(cur):
            j = i + 1
            merged = cur.strip()
            # merge beberapa baris berikutnya kalau juga ALLCAPS dan pendek
            while j < len(lines) and is_allcaps_line(lines[j]) and len(lines[j].strip()) <= 40:
                merged += " " + lines[j].strip()
                j += 1
            out.append(merged)
            i = j
            continue

        out.append(cur)
        i += 1

    return "\n".join(out)


def dehyphenate(text: str) -> str:
    """
    Gabungkan kata terpotong karena line-break:
      "per-\nkara" -> "perkara"
    """
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


# ============================================================
# Fungsi utama untuk hapus watermark + header + footer (LEVEL PDF)
# ============================================================
def remove_watermark_and_headers(wmText, inputFile, outputFile):
    """
    Menghapus watermark, header, dan footer berbasis teks dari file PDF.
    Fix:
      - /Contents multi-stream tidak overwrite
      - Operator TJ ditangani dengan benar (array)
    """
    try:
        with open(inputFile, "rb") as f:
            source = PdfFileReader(f, "rb")
            output = PdfFileWriter()

            # Pattern umum header/footer putusan MA
            patterns = [
                r"(?i)ahkama\s*$",
                r"(?i)ahkamah\s+agung\s+republ",
                r"(?i)mahkamah\s+agung\s+republik\s+indonesia",
                r"(?i)h\s+agung\s+republik\s+indonesi",
                r"(?i)ik\s+indones",
                r"(?i)direktori\s+putusan\s+mahkamah\s+agung",
                r"(?i)putusan\.mahkamahagung\.go\.id",
                r"(?i)^disclaimer\s*$",
                r"(?i)kepaniteraan\s+mahkamah\s+agung\s+republik\s+indonesia",
                r"(?i)berusaha\s+untuk\s+selalu\s+mencantumkan",
                r"(?i)pelaksanaan\s+fungsi\s+peradilan",
                r"(?i)dalam\s+hal\s+anda\s+menemukan",
                r"(?i)dalam\s+hal\s+.*\s+menemukan\s+inakurasi",
                r"(?i)email\s*:\s*kepaniteraan@mahkamahagung\.go\.id",
                r"(?i)telp\s*:\s*021-?384\s*3348",
                r"(?i)halaman\s+\d+\s+dari\s+\d+\s+halaman",
                r"(?i)halaman\s+\d+\s*$",
                r"(?i)hal\s+\d+\s+putusan\s+no\..*$",  # tambahan: "Hal 5 Putusan No..."
                r"(?i)putusan\s+nomor\s+\d+.*$",
                r"(?i)untuk\s+salinan\s*$",
                r"(?i)ditandatangani\s+secara\s+elektronik",
                r"(?i)^ttd\.?\s*$",
                r"(?i)^nip\.?\s*\d+",
            ]

            for page_num in range(source.getNumPages()):
                page = source.getPage(page_num)

                # Handle multiple content streams
                content_object = page["/Contents"].getObject()
                if not isinstance(content_object, list):
                    content_object = [content_object]

                new_streams = []

                for obj in content_object:
                    content = ContentStream(obj, source)

                    for operands, operator in content.operations:
                        if operator not in [b_("Tj"), b_("TJ")]:
                            continue

                        # Ambil teks dari operasi
                        extracted = ""
                        if operator == b_("TJ"):
                            # TJ berisi array: campuran string dan angka kerning
                            arr = operands[0]
                            if isinstance(arr, list):
                                for item in arr:
                                    if isinstance(item, TextStringObject):
                                        extracted += str(item)
                                    elif isinstance(item, bytes):
                                        extracted += item.decode("utf-8", errors="ignore")
                                    elif isinstance(item, str):
                                        extracted += item
                        else:
                            # Tj
                            v = operands[0]
                            if isinstance(v, bytes):
                                extracted = v.decode("utf-8", errors="ignore")
                            else:
                                extracted = str(v)

                        should_remove = False

                        # 1) Watermark spesifik yang terdeteksi
                        for wm in wmText:
                            if wm.lower() in extracted.lower():
                                should_remove = True
                                break

                        # 2) Header/footer umum
                        if not should_remove:
                            for p in patterns:
                                if re.search(p, extracted.strip()):
                                    should_remove = True
                                    break

                        # Blank-kan teks kalau match
                        if should_remove:
                            if operator == b_("Tj"):
                                operands[0] = TextStringObject("")
                            else:
                                # TJ: blank-kan hanya elemen string, jangan ganti array jadi string
                                arr = operands[0]
                                if isinstance(arr, list):
                                    new_arr = []
                                    for item in arr:
                                        if isinstance(item, (TextStringObject, str, bytes)):
                                            new_arr.append(TextStringObject(""))
                                        else:
                                            new_arr.append(item)  # angka kerning dll
                                    operands[0] = new_arr
                                else:
                                    operands[0] = []

                    new_streams.append(content)

                # Set kembali /Contents (jangan overwrite per-stream)
                if len(new_streams) == 1:
                    page.__setitem__(NameObject("/Contents"), new_streams[0])
                else:
                    page.__setitem__(NameObject("/Contents"), ArrayObject(new_streams))

                output.addPage(page)

            with open(outputFile, "wb") as outputStream:
                output.write(outputStream)

        return True

    except Exception as e:
        print(f"❌ Error removing watermark from {inputFile}: {str(e)}")
        return False


# ============================================================
# Ekstraksi teks dari PDF dan preprocessing (LEVEL TEXT)
# ============================================================
def extract_clean_text(pdf_path, txt_output):
    """
    Ekstrak teks dari PDF dan bersihkan dengan normalisasi.
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""

        for page in doc:
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            page_text = "\n".join([b[4] for b in blocks if b[4].strip()])
            text += page_text + "\n"

        doc.close()

        # Pipeline preprocessing teks
        text = normalize_unicode_artifacts(text)
        text = dehyphenate(text)
        text = normalize_paragraphs_and_spacing(text)
        text = remove_remaining_artifacts(text)
        text = fix_spaced_letters(text, min_letters=3)
        text = merge_label_colon_lines(text)

        text = merge_allcaps_lines(text)
        text = fix_glued_words(text)

        with open(txt_output, "w", encoding="utf-8") as f:
            f.write(text.strip())

        return True

    except Exception as e:
        print(f"❌ Error extracting text from {pdf_path}: {str(e)}")
        return False


# ============================================================
# Normalisasi paragraf + spasi + gabung line-break yang “pecah”
# ============================================================
def normalize_paragraphs_and_spacing(text):
    # Ganti karakter non-printable
    text = text.replace("\xa0", " ").replace("\t", " ")
    text = re.sub(r"\r\n", "\n", text)

    # Gabungkan huruf kapital terpisah spasi (contoh: M A H K A M A H → MAHKAMAH)
    text = re.sub(
        r"\b(?:[A-Z]\s){2,}[A-Z]\b",
        lambda m: m.group(0).replace(" ", ""),
        text,
    )

    # Hapus spasi berlebih
    text = re.sub(r" {2,}", " ", text)

    # Hilangkan newline yang bukan penanda akhir kalimat
    # Tambahan: anggap bullet "•" sebagai awal list, jangan digabung
    text = re.sub(
        r"(?<![.!?:;])\n(?!\s*\n|[A-Z][A-Z]+|[•\-–—]|Hal\b|Nama|Tempat|Umur|Jenis|Kewarganegaraan|Tempat Tinggal|Agama|Pekerjaan|Terdakwa)",
        " ",
        text,
    )

    # Ganti beberapa newline kosong jadi satu
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Rapikan spasi sebelum dan sesudah tanda baca
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([.,;:!?])(?=[A-Za-z])", r"\1 ", text)

    return text.strip()


# ============================================================
# Hapus sisa-sisa artifact setelah ekstraksi (LEVEL TEXT)
# ============================================================
def remove_remaining_artifacts(text):
    """
    Hapus sisa watermark, header, footer yang masih ada di teks.
    """
    lines = text.split("\n")
    cleaned_lines = []

    skip_patterns = [
        r"^\s*ahkama\s*$",
        r"^\s*ahkamah\s+agung\s+republ\s*$",
        r"^\s*mahkamah\s+agung\s+republik\s+indonesia\s*$",
        r"^\s*h\s+agung\s+republik\s+indonesi\s*$",
        r"^\s*ik\s+indones\s*$",
        r"^\s*direktori\s+putusan",
        r"^\s*putusan\.mahkamahagung\.go\.id\s*$",
        r"^\s*halaman\s+\d+\s+dari\s+\d+",
        r"^\s*halaman\s+\d+\s*$",
        r"^\s*hal\s+\d+\s+putusan\s+no\..*$",   # tambahan: Hal X Putusan No....
        r"^\s*disclaimer\s*$",
        r"^\s*kepaniteraan\s+mahkamah\s+agung",
        r"berusaha\s+untuk\s+selalu\s+mencantumkan",
        r"pelaksanaan\s+fungsi\s+peradilan",
        r"dalam\s+hal\s+.*\s+menemukan",
        r"email\s*:\s*kepaniteraan@",
        r"telp\s*:\s*021-?384",
        r"^\s*untuk\s+salinan\s*$",
    ]

    skip_next = 0
    for line in lines:
        if skip_next > 0:
            skip_next -= 1
            continue

        line_stripped = line.strip()

        # Skip baris kosong di awal
        if not line_stripped and not cleaned_lines:
            continue

        should_skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line_stripped, re.IGNORECASE):
                should_skip = True
                # Jika disclaimer, skip beberapa baris berikutnya (footer MA)
                if "disclaimer" in line_stripped.lower():
                    skip_next = 6
                break

        if not should_skip:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


# ============================================================
# Deteksi watermark
# ============================================================
def watermark_text(inputFile, waterMarkTextStarting):
    """
    Deteksi watermark yang ada di halaman pertama PDF.
    """
    wmText = []
    try:
        with open(inputFile, "rb") as pdfFileObj:
            pdfReader = PyPDF2.PdfReader(pdfFileObj)

            if len(pdfReader.pages) == 0:
                return wmText

            first_page = pdfReader.pages[0]
            text = first_page.extract_text() or ""

            for wm in waterMarkTextStarting:
                if wm.lower() in text.lower():
                    wmText.append(wm)

        return wmText

    except Exception as e:
        print(f"⚠️  Warning: Could not detect watermark in {inputFile}: {str(e)}")
        return waterMarkTextStarting


# ============================================================
# Utility dan pipeline utama
# ============================================================
def draw():
    """Tampilkan header program."""
    print("\n" + "=" * 60)
    print(" 🧹 PUTUSAN WATERMARK + HEADER/FOOTER REMOVER")
    print("=" * 60 + "\n")


def creatingFolder(dirName):
    """Buat folder jika belum ada."""
    Path(dirName).mkdir(parents=True, exist_ok=True)
    return dirName


def CheckingFiles(dirName):
    """
    Cek keberadaan file PDF di folder input.
    """
    dir_path = Path(dirName)

    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Folder '{dirName}' created.")

    print(f"📂 Looking for PDF files in '{dirName}'...")
    input(f"   Place PDF files in '{dirName}' and Press Enter...")

    while True:
        files = [f for f in os.listdir(dirName) if f.lower().endswith(".pdf")]

        if len(files) == 0:
            print("⚠️  No PDF files found!")
            input(f"   Add PDF files to '{dirName}' and Press Enter...")
        else:
            break

    print(f"✅ Found {len(files)} PDF file(s)\n")
    return files


def processingFilesInFolder(inputDir, outputDir, files, waterMarkTextStarting):
    """
    Proses semua file PDF: hapus watermark dan ekstrak teks.
    """
    print("🔄 Processing files...\n")

    success_count = 0
    failed_count = 0

    for idx, name in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] Processing: {name}")

        inputFile = os.path.join(inputDir, name)
        temp_pdf = os.path.join(outputDir, f"temp_{name}")
        txt_output = os.path.join(outputDir, name.replace(".pdf", ".txt"))

        try:
            # Deteksi watermark
            wm_text = watermark_text(inputFile, waterMarkTextStarting)

            # Hapus watermark dari PDF
            if remove_watermark_and_headers(wm_text, inputFile, temp_pdf):
                # Ekstrak teks dari PDF yang sudah dibersihkan
                if extract_clean_text(temp_pdf, txt_output):
                    print(f"   ✓ Success → {txt_output}")
                    success_count += 1
                else:
                    print("   ✗ Failed to extract text")
                    failed_count += 1

                # Hapus PDF temporary
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
            else:
                print("   ✗ Failed to remove watermark")
                failed_count += 1

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            failed_count += 1
            if os.path.exists(temp_pdf):
                try:
                    os.remove(temp_pdf)
                except:
                    pass

        print()

    return success_count, failed_count


def verbosity(success, failed, outputDir):
    """
    Tampilkan ringkasan hasil pemrosesan.
    """
    print("=" * 60)
    print(f"✅ Successfully processed: {success} file(s)")
    if failed > 0:
        print(f"❌ Failed: {failed} file(s)")
    print(f"📁 Results saved in: '{outputDir}'")
    print("=" * 60 + "\n")


def main():
    """
    Fungsi utama program.
    """
    draw()

    waterMarkTextStarting = [
        "Mahkamah Agung",
        "ahkamah",
        "Direktori Putusan",
        "Halaman",
        "Disclaimer",
    ]

    inputDir = "../data/teroris"
    outputDir = "../Cleaned-Doc/"

    try:
        creatingFolder(outputDir)
        files = CheckingFiles(inputDir)

        success, failed = processingFilesInFolder(
            inputDir, outputDir, files, waterMarkTextStarting
        )

        verbosity(success, failed, outputDir)

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user.")
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")

    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
