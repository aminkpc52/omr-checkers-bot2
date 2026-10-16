# Bot Telegram Semakan OMR Automatik

Bot ini membolehkan anda:
1. Menjana borang OMR sendiri (20 soalan, pilihan A-D, dengan medan Nama & Kelas) — `/generate`
2. Urus **berbilang kelas** melalui butang — `/kelas` (tambah kelas, masukkan/tukar skema jawapan setiap kelas)
3. Semakan automatik — pilih kelas → "Semak Jawapan" → upload gambar; bot terus menganalisis sebaik gambar diterima
4. Gambar **tidak disimpan ke cakera** — dimuat turun & diproses terus dalam memori (lihat `handle_photo()` dalam `bot.py`)
5. **Analisis A/B/C/D terkumpul setiap kelas** — bot rekod jawapan yang dikesan bagi setiap gambar yang disemak, dan "Jana Analisis Penuh" memaparkan berapa ramai jawab A/B/C/D bagi setiap soalan
6. Reset sesi — `/reset`
7. **🗑️ Reset Semua** (butang) — padam SEMUA kelas/skema/analisis tersimpan & mula semula (ada skrin pengesahan dahulu)

Borang OMR kini dijana pada saiz **A4 sebenar (827×1169px @ 100 DPI)** — fail lebih kecil/ringan berbanding versi awal, tetapi apabila dicetak tetap tepat 210mm × 297mm memandangkan metadata DPI turut dibenamkan dalam PNG.

## Struktur fail

```
omr_telegram_bot/
├── bot.py              # Entrypoint utama — command handler + butang (inline keyboard) Telegram
├── omr_layout.py        # Koordinat borang (dikongsi generator & scanner)
├── omr_generator.py     # Jana borang OMR kosong (imej PNG dalam memori)
├── omr_scanner.py       # Baca gambar OMR, betulkan perspektif, kira markah, tanda warna
├── class_manager.py      # Urus kelas: skema jawapan + rekod analisis A/B/C/D (JSON kecil, bukan gambar)
├── requirements.txt
└── class_store.json      # Dijana automatik selepas kelas pertama ditambah
```

## Persediaan dalam Visual Studio Code

1. **Buka folder ini** dalam VS Code (File > Open Folder).
2. Pastikan extension **Python** (Microsoft) dipasang.
3. Buka Terminal dalam VS Code (`` Ctrl+` ``) dan jalankan:

   ```bash
   python -m venv venv
   ```

   Aktifkan virtual environment:
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Windows (cmd): `venv\Scripts\activate.bat`
   - macOS/Linux: `source venv/bin/activate`

4. Pasang kebergantungan:

   ```bash
   pip install -r requirements.txt
   ```

5. **Dapatkan token bot Telegram** daripada **@BotFather** di Telegram (`/newbot`).

6. **Tetapkan token** — environment variable disyorkan:
   - Windows (PowerShell): `$env:TELEGRAM_BOT_TOKEN="token_anda"`
   - macOS/Linux: `export TELEGRAM_BOT_TOKEN="token_anda"`
   - Atau edit terus baris `BOT_TOKEN` dalam `bot.py`.

7. Jalankan bot (tekan `F5` dalam VS Code, atau `python bot.py`). Pastikan **hanya SATU** salinan bot berjalan pada satu masa (ralat `Conflict` akan berlaku jika lebih daripada satu instance polling serentak).

## Cara guna bot (di Telegram)

1. `/kelas` — papar senarai kelas + butang **➕ Tambah Kelas Baru**
2. Tekan **➕ Tambah Kelas Baru**, taip nama kelas (cth: `5 Bestari`) dan hantar
3. Selepas kelas dicipta, menu kelas dipaparkan dengan 3 butang:
   - **📝 Masukkan Skema Baru** — taip 20 huruf (cth: `ABCDABCDABCDABCDABCD`) dan hantar; ini akan **menggantikan** skema sedia ada bagi kelas itu
   - **📷 Semak Jawapan (Upload Gambar)** — bot minta gambar; hantar gambar OMR yang telah diisi, bot terus proses & rekod jawapan. Boleh hantar **banyak gambar berturut-turut** untuk kelas yang sama (satu gambar = satu pelajar)
   - **📊 Jana Analisis Penuh** — papar jumlah A/B/C/D (+ Kosong/Berganda) bagi **setiap soalan**, dikumpul daripada semua gambar yang telah disemak untuk kelas itu
4. Guna butang **🔙 Kembali ke Senarai Kelas** untuk tukar/tambah kelas lain
5. `/generate` — dapatkan borang OMR kosong (ada medan Nama & Kelas)
6. `/reset` — kosongkan sesi semasa (kelas & skema yang telah disimpan dikekalkan)

## Nota teknikal & had penting

- **Kamera automatik:** API Bot Telegram tidak membenarkan bot mengawal/trigger kamera peranti pengguna secara terus. "Semak Jawapan" bermaksud bot memproses gambar secara automatik & serta-merta sebaik ia diupload, tanpa sebarang langkah manual tambahan.
- **Ketepatan pengesanan:** Pengesanan gelembung guna analisis kepekatan piksel (fill-ratio) selepas pembetulan perspektif melalui 4 penanda ArUco di penjuru borang. Untuk hasil terbaik: pastikan pencahayaan cukup terang, ke-4 penjuru borang kelihatan penuh dalam gambar, dan gelembung dihitamkan dengan jelas.
- **Boleh laras:** Nilai `FILL_THRESHOLD` dalam `omr_scanner.py` (lalai 0.35) boleh dilaraskan jika terlalu ketat/longgar berdasarkan ujian sebenar.
- **Privasi gambar:** `handle_photo()` dalam `bot.py` memuat turun gambar terus ke `bytearray` dalam memori dan tidak sekali-kali menulisnya ke cakera; rujukan bait imej turut dilupuskan (`del image_bytes`) selepas pemprosesan.
- **Apa yang disimpan (bukan gambar):** `class_manager.py` simpan dalam `class_store.json` — nama kelas, skema jawapan, dan **jawapan yang dikesan** (huruf A/B/C/D/Kosong/Berganda sahaja) bagi setiap gambar yang disemak. Ini membolehkan "Jana Analisis Penuh" berfungsi walaupun bot dimulakan semula. Imej sendiri tidak pernah disimpan di sini.
- **Setiap kelas berasingan:** skema jawapan dan rekod analisis satu kelas tidak bercampur dengan kelas lain — dikenal pasti melalui `class_id` unik yang dijana automatik.

## Kemas kini / pelarasan lanjut yang mungkin berguna

- Butang "Padam Kelas" / "Reset Analisis Kelas" (buang semua submission tanpa buang skema)
- Eksport analisis penuh kepada Excel/CSV
- Sokongan bilangan pilihan berbeza (cth. A-E) — ubah `OPTIONS` dalam `omr_layout.py`
- Sokongan lebih 20 soalan — ubah `TOTAL_QUESTIONS` & `QUESTIONS_PER_COLUMN`