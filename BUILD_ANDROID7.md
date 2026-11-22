# Build XStreaming untuk Android 7 (Galaxy Tab A 8.0 SM-P355)

APK resmi XStreaming butuh Android 8.0. Build lokal ini menurunkan minSdk ke 24 (Android 7.0)
dan hanya untuk ARMv7 (`armeabi-v7a`).

## Perubahan dari upstream

| File | Perubahan |
|---|---|
| `android/build.gradle` | `minSdkVersion` 26 → 24; `google()`/`mavenCentral()` sebelum mirror Aliyun |
| `android/app/build.gradle` | CMake `-D__ANDROID_UNAVAILABLE_SYMBOLS_ARE_WEAK__` (simbol API 26+ di LSFG jadi weak) |
| `android/app/src/main/java/com/xstreaming/FullScreenManager.java` | `WebView.getCurrentWebViewPackage()` → `WebViewCompat.getCurrentWebViewPackage(context)` |
| `android/app/src/main/java/com/xstreaming/XalManager.java` | `java.util.Base64`/`java.time.Instant` → `android.util.Base64`/`System.currentTimeMillis()` |
| `android/app/build.gradle`, `MainApplication.java` | **Umeng analytics dihapus** (dependensi + init) |
| `src/pages/NativeStream.tsx` | `getStats()` untuk laporan sesi tiap 5 detik (1 detik hanya saat panel performa tampil) |
| `src/webrtc/Driver/Gamepad.ts` | State controller dikirim hanya saat berubah + heartbeat 100 ms (dulu selalu 62,5×/detik) |
| `src/pages/NativeStream.tsx` | Log `[XSPERF]` 1×/detik saat panel performa tampil (untuk `bench/bench_xstreaming.sh`) |

Pemeriksaan `SDK_INT` lain di kode upstream otomatis berfungsi lagi karena build menargetkan API 24.

## Toolchain

- JDK 17 (Corretto 17), Android SDK, NDK `23.1.7779620`
- Node 22 + **Yarn 4.2.2** lewat corepack (lockfile berformat Yarn 4, jangan pakai Yarn 1)
- Rust stable + target `armv7-linux-androideabi` (rustup, `~/.cargo/bin`)

## Langkah

```bash
cd XStreaming
export PATH="$HOME/.nvm/versions/node/v22.12.0/bin:$HOME/.cargo/bin:$PATH" COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack yarn@4.2.2 install          # postinstall patch-package gagal di patch react-native-paper (file patch upstream rusak)
for p in patches/react-native-paper+5.12.5.patch patches/react-native-webrtc+124.0.5.patch patches/react-native-webview+13.10.5.patch; do patch -p1 --forward -i "$p"; done
cd android
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties
export JAVA_HOME=$HOME/Library/Java/JavaVirtualMachines/corretto-17.0.18/Contents/Home
./gradlew assembleProdRelease -PreactNativeArchitectures=armeabi-v7a \
  -PXSTREAMING_RELEASE_STORE_FILE=$HOME/.android/debug.keystore \
  -PXSTREAMING_RELEASE_STORE_PASSWORD=android \
  -PXSTREAMING_RELEASE_KEY_ALIAS=androiddebugkey \
  -PXSTREAMING_RELEASE_KEY_PASSWORD=android
adb install -r app/build/outputs/apk/prod/release/app-prod-release.apk
```

Setelah `adb install`, Play Store 54.x di Android 7 menampilkan "Google Play Store terhenti"
(bug Play Protect di perangkat ini). Install tetap berhasil; tutup saja dialognya.

## Hasil di SM-P355 (Remote Play Xbox Series S, Wi-Fi 5 GHz satu jaringan dengan Xbox)

| | Better xCloud (WebView) | XStreaming build ini (Native) |
|---|---|---|
| Frame tampil per detik | ~21 | **58–60** (SurfaceFlinger) |
| Frame terbuang | ~56% | **0** (`EglRenderer: Dropped: 0`, render ~0,7 ms/frame) |
| CPU sistem sibuk (`top`) | ~95% | **~64%** |

Setelah optimasi (Umeng dihapus, `getStats` jarang, input saat berubah), diukur dengan
`bench/bench_xstreaming.sh`: CPU app −17% (1,51 → 1,25 core), jeda frame > 33 ms 18 → 12,
waktu render 802 → 633 µs, GC 6 → 1 per menit. Detail: [`bench/COMPARISON.md`](bench/COMPARISON.md).

## Benchmark

Jalankan saat stream sedang berjalan (tablet tersambung ADB):

```bash
bench/bench_xstreaming.sh <label> 60
```

Mengukur frame yang benar-benar tampil (SurfaceFlinger), statistik renderer WebRTC, CPU app/sistem
dan per-thread, memori, GC, bitrate, suhu. Jika panel performa XStreaming tampil (tahan ≡ 2 detik →
"Tampilkan/sembunyikan performa"), juga merangkum decode time, jitter, dan RTT dari log `[XSPERF]`.
Hasil disimpan di `bench/results/` (tidak di-commit).

## Catatan

- Mesin render: **Native** (bawaan). Opsi lain: Nano (Rust, eksperimental) dan WebView.
- Frame generation (LSFG) butuh Vulkan; GPU Adreno 306 tidak mendukung Vulkan, jadi fitur itu tidak jalan.
- SDK analitik Umeng dari upstream (`com.umeng.umsdk:common`/`asms`) dihapus di fork ini.
- "Dekoding latensi ultra rendah" berfungsi di Snapdragon 410 (decode 13 → 10,2 ms) tapi menambah CPU
  dan jeda frame kecil; untuk perangkat ini dibiarkan nonaktif. Lihat `bench/COMPARISON.md`.
