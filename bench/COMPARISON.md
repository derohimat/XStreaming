# XStreaming di SM-P355: baseline vs optimized

Remote Play Xbox Series S, 720p60, Wi-Fi 5 GHz satu jaringan dengan Xbox, sama-sama diukur
60 detik saat pertandingan berjalan (bitrate setara: 5,93 vs 6,03 Mbps).
Skrip: `bench/bench_xstreaming.sh <label> 60` (dari root repo).

| Metrik | Baseline | Optimized | Perubahan |
|---|---|---|---|
| Frame tampil (rata-rata) | 59,6 fps | 59,7 fps | sama (sudah mentok 60 Hz) |
| fps per detik: min / p10 | 57 / 58 | 57 / 59 | sedikit lebih stabil |
| Jeda frame > 33 ms | 18 | **12** | −33% |
| Jeda frame > 50 ms / maks | 2 / 67 ms | 2 / 67 ms | sama |
| Frame dibuang renderer | 0 | 0 | sama |
| Waktu render per frame | 802 µs | **633 µs** | −21% |
| CPU app | 150,7% core | **125,3% core** | **−17%** |
| CPU sistem sibuk | 58,5% | **52,7%** | −5,8 poin |
| Memori (PSS) | 215 MB | **139 MB** | −35%* |
| GC selama 60 detik | 6 | **1** | −83% |
| Log dari JS | 63 baris | 12 baris | −81% |

\* Baseline diukur pada proses yang sudah berjalan lama; optimized pada proses baru setelah install.
Sebagian penurunan memori karena usia proses, sebagian karena Umeng dihapus.

## CPU per thread (% dari satu core)

| Thread | Baseline | Optimized |
|---|---|---|
| worker_thread (WebRTC) | 21,1 | 17,4 |
| network_thread (WebRTC) | 19,7 | 15,6 |
| EglThread (render) | 16,2 | 13,0 |
| mqt_js (JavaScript) | 15,4 | 12,6 |
| JNISurfaceTexture | 12,1 | 9,5 |
| AudioTrackJavaThread | 11,0 | 9,4 |
| com.xstreaming (UI) | 9,3 | 11,6 |
| mqt_native_modules | 7,0 | 6,0 |

Thread WebRTC ikut turun karena `getStats()` dan pengiriman lewat data channel (SCTP)
dikerjakan di thread worker/network WebRTC.

## Perubahan

1. Umeng analytics dihapus (dependensi Gradle + init di `MainApplication.java`).
2. `src/pages/NativeStream.tsx`: `getStats()` untuk laporan sesi tiap 5 detik (tetap 1 detik saat panel performa tampil).
3. `src/webrtc/Driver/Gamepad.ts`: state controller hanya diantrekan saat berubah + heartbeat 100 ms
   (sebelumnya selalu dikirim 62,5×/detik walau controller diam).

Run ulang tanpa panel (`nama-label`, saat menu jeda game): CPU app 123,5% core, jeda > 33 ms 10.
Hasilnya dekat dengan run optimized, jadi variasi antar-run kecil.

## Uji "Dekoding latensi ultra rendah" (2026-11-21)

Wrapper `LowLatencyVideoDecoder` terpasang di `OMX.qcom.video.decoder.avc`; gambar normal (tanpa hitam/kedip).

| Metrik | Dekoder normal | Latensi ultra rendah |
|---|---|---|
| Waktu decode (laporan sesi, rata-rata) | 13 ms | **10,2 ms** |
| Waktu decode (panel, median) | 12,5 ms | (panel tidak bisa dinyalakan) |
| Jitter (laporan sesi) | 4,6 ms | 4,3 ms |
| Latensi jaringan (laporan sesi) | 5 ms | 5 ms |
| fps rata-rata / min per detik (tanpa panel) | 59,7 / 57 | 59,4 / 58 |
| Jeda frame > 33 ms per menit (tanpa panel) | **12** | 33 |
| Jeda terlama (tanpa panel) | 67 ms | **50 ms** |
| CPU app (tanpa panel) | **125% core** | 143% core |

Kesimpulan: decode ~2,5–3 ms lebih cepat (~20%), dibayar CPU +18 poin dan jeda kecil hampir 3×.

## Catatan lain

- Panel performa XStreaming berat di perangkat ini: dengan panel tampil CPU app naik 125 → 166% core
  dan jeda > 33 ms naik 12 → 55 per menit. Nyalakan hanya saat perlu.
- Setelan "Tampilkan performa" (selalu tampil) tidak dibaca oleh mode render Native (`NativeStream.tsx`);
  panel hanya bisa dinyalakan lewat menu ≡ (tahan 2 detik) → "Tampilkan/sembunyikan performa".
