# Media Downloader v0.3

نسخة Android مبنية بـ Flet + yt-dlp، مع QuickJS وFFmpeg مضمّنين في APK.

## المكونات
- Flet 0.86.2
- yt-dlp 2026.07.04
- yt-dlp-ejs 0.8.0 عبر `yt-dlp[default]`
- QuickJS NG 0.15.1 مبني لـ Android arm64-v8a داخل GitHub Actions
- FFmpeg 8.1.2 Android arm64 مضمّن في APK

## الوظائف
- تحليل الروابط العامة التي يدعمها yt-dlp.
- فيديو: أفضل جودة أو 1080p/720p/480p/360p.
- صوت: استخراج MP3 بجودة 192 kbps.
- دمج video + audio بواسطة FFmpeg.
- شريط تقدم وحفظ الملف عبر Android FilePicker.

## البناء
Actions → Build Media Downloader APK → Run workflow


## Multi-site support
The app uses yt-dlp's generic extractors instead of hard-coding one platform.
Common platforms include YouTube, Facebook, Instagram, TikTok, X/Twitter,
Vimeo, Dailymotion, Reddit and Twitch, subject to each site's current support.
