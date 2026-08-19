import asyncio
import importlib.resources as resources
import os
import re
import threading
from pathlib import Path

import flet as ft
import yt_dlp


APP_NAME = "Media Downloader"
DOWNLOAD_DIR = Path(os.environ.get("FLET_APP_STORAGE_DATA", Path.home())) / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(name: str, default: str = "media") -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name or default).strip()
    return name[:150] or default


def format_duration(seconds):
    if not seconds:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def tool_resource(name):
    return resources.files("assets").joinpath("bin", name)


def with_tools(callback):
    """Run a yt-dlp callback with packaged QuickJS and FFmpeg available."""
    try:
        qjs = tool_resource("qjs")
        ffmpeg = tool_resource("ffmpeg")
        with resources.as_file(qjs) as qjs_path, resources.as_file(ffmpeg) as ffmpeg_path:
            if not qjs_path.exists():
                raise FileNotFoundError("QuickJS runtime is missing from the APK")
            if not ffmpeg_path.exists():
                raise FileNotFoundError("FFmpeg is missing from the APK")

            for path in (qjs_path, ffmpeg_path):
                try:
                    path.chmod(path.stat().st_mode | 0o111)
                except OSError:
                    pass

            common = {
                "js_runtimes": {"quickjs": {"path": str(qjs_path)}},
                "remote_components": {"ejs:github"},
                "ffmpeg_location": str(ffmpeg_path),
            }
            return callback(common)
    except Exception as ex:
        raise RuntimeError(f"Runtime tools initialization failed: {ex}") from ex


async def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 18
    page.scroll = ft.ScrollMode.AUTO
    page.bgcolor = "#0f172a"

    url_field = ft.TextField(
        label="رابط الفيديو أو الصوت",
        hint_text="https://...",
        prefix_icon=ft.Icons.LINK,
        text_align=ft.TextAlign.LEFT,
        expand=True,
        border_radius=14,
    )

    analyze_button = ft.Button(
        content="تحليل",
        icon=ft.Icons.SEARCH,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=16,
        ),
    )

    status = ft.Text("", color="#94a3b8")
    progress = ft.ProgressBar(value=0, visible=False)
    title_text = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
    details_text = ft.Text("", color="#94a3b8")
    thumbnail = ft.Image(
        src="",
        width=320,
        height=190,
        fit=ft.BoxFit.COVER,
        border_radius=ft.BorderRadius.all(14),
        visible=False,
    )

    mode = ft.Dropdown(
        label="نوع الملف",
        value="video",
        options=[
            ft.DropdownOption(key="video", text="🎬 فيديو"),
            ft.DropdownOption(key="audio", text="🎵 صوت"),
        ],
        width=220,
        border_radius=14,
    )

    quality = ft.Dropdown(
        label="الجودة",
        value="best",
        options=[
            ft.DropdownOption(key="best", text="أفضل جودة متاحة"),
            ft.DropdownOption(key="1080", text="1080p"),
            ft.DropdownOption(key="720", text="720p"),
            ft.DropdownOption(key="480", text="480p"),
            ft.DropdownOption(key="360", text="360p"),
        ],
        width=220,
        border_radius=14,
    )

    info_card = ft.Container(
        visible=False,
        padding=16,
        border_radius=18,
        bgcolor="#111827",
        content=ft.Column([thumbnail, title_text, details_text], spacing=10),
    )

    download_button = ft.Button(
        content="بدء التحميل",
        icon=ft.Icons.DOWNLOAD,
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=16,
        ),
    )

    save_button = ft.Button(
        content="حفظ في الجهاز",
        icon=ft.Icons.SAVE_ALT,
        visible=False,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=16,
        ),
    )

    result_text = ft.Text("", color="#cbd5e1")
    current_info = {"data": None}
    current_file = {"path": None}

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def extractor_options(base=None):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "js_runtimes": {"quickjs": {"path": None}},
            "remote_components": {"ejs:github"},
        }
        if base:
            opts.update(base)
        return opts

    async def analyze(_):
        url = (url_field.value or "").strip()
        if not url:
            status.value = "أدخل رابطًا أولًا."
            page.update()
            return

        analyze_button.disabled = True
        download_button.disabled = True
        save_button.visible = False
        info_card.visible = False
        thumbnail.visible = False
        progress.visible = False
        status.value = "⏳ جاري تحليل الرابط..."
        page.update()

        def extract():
            def run(extra):
                opts = extractor_options({
                    "skip_download": True,
                    "extract_flat": False,
                    "format": None,
                })
                opts.update(extra)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            return with_tools(run)

        try:
            data = await asyncio.to_thread(extract)
            current_info["data"] = data
            title_text.value = data.get("title") or "بدون عنوان"
            details_text.value = (
                f"المنصة/الناشر: {data.get('uploader') or '—'}  •  "
                f"المدة: {format_duration(data.get('duration'))}"
            )
            thumb = data.get("thumbnail")
            if thumb:
                thumbnail.src = thumb
                thumbnail.visible = True
            info_card.visible = True
            download_button.disabled = False
            status.value = "✅ تم تحليل الرابط."
        except Exception as ex:
            status.value = f"❌ تعذر تحليل الرابط: {ex}"
        finally:
            analyze_button.disabled = False
            page.update()

    analyze_button.on_click = analyze


    def detect_site(url: str) -> str:
        try:
            host = urlparse(url).netloc.lower().split(":")[0]
        except Exception:
            return "موقع غير معروف"
        if host.endswith(("youtube.com", "youtu.be")):
            return "YouTube"
        if host.endswith(("facebook.com", "fb.watch")):
            return "Facebook"
        if host.endswith(("instagram.com", "instagr.am")):
            return "Instagram"
        if host.endswith(("tiktok.com", "vm.tiktok.com")):
            return "TikTok"
        if host.endswith(("twitter.com", "x.com", "t.co")):
            return "X / Twitter"
        if host.endswith("vimeo.com"):
            return "Vimeo"
        if host.endswith(("dailymotion.com", "dai.ly")):
            return "Dailymotion"
        if host.endswith(("reddit.com", "redd.it")):
            return "Reddit"
        if host.endswith("twitch.tv"):
            return "Twitch"
        return "موقع مدعوم آخر"

    def choose_format():
        selected_mode = mode.value
        selected_quality = quality.value
        if selected_mode == "audio":
            return "bestaudio/best"
        if selected_quality == "best":
            return "bestvideo*+bestaudio/best"
        h = int(selected_quality)
        return f"bestvideo*[height<={h}]+bestaudio/best[height<={h}]/best"

    def start_download(_):
        data = current_info["data"]
        url = (url_field.value or "").strip()
        if not data or not url:
            return

        download_button.disabled = True
        save_button.visible = False
        progress.visible = True
        progress.value = 0
        result_text.value = f"⏳ جاري تنزيل {detect_site(url)}..."
        status.value = ""
        page.update()

        fmt = choose_format()
        base_name = safe_filename(data.get("title"), "media")

        def worker():
            def hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    done = d.get("downloaded_bytes", 0)
                    value = (done / total) if total else 0
                    page.run_task(update_progress, min(value, 0.99))
                elif d["status"] == "finished":
                    page.run_task(update_progress, 0.99)

            template = str(DOWNLOAD_DIR / f"{base_name}.%(ext)s")

            def run(extra):
                opts = extractor_options({
                    "format": fmt,
                    "outtmpl": template,
                    "progress_hooks": [hook],
                    "merge_output_format": "mp4",
                })
                if mode.value == "audio":
                    opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]
                opts.update(extra)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return Path(ydl.prepare_filename(info))

            try:
                prepared = with_qjs(run)
                candidates = list(DOWNLOAD_DIR.glob(f"{base_name}.*"))
                if prepared.exists():
                    final_path = prepared
                elif candidates:
                    final_path = max(candidates, key=lambda p: p.stat().st_mtime)
                else:
                    raise RuntimeError("لم يتم العثور على الملف بعد التنزيل.")
                current_file["path"] = final_path
                page.run_task(download_done, final_path)
            except Exception as ex:
                page.run_task(download_failed, str(ex))

        threading.Thread(target=worker, daemon=True).start()

    async def update_progress(value):
        progress.value = value
        page.update()

    async def download_done(path):
        progress.value = 1
        result_text.value = f"✅ اكتمل التنزيل: {path.name}"
        save_button.visible = True
        download_button.disabled = False
        page.update()

    async def download_failed(message):
        progress.visible = False
        result_text.value = f"❌ فشل التنزيل: {message}"
        download_button.disabled = False
        page.update()

    async def save_file(_):
        path = current_file["path"]
        if not path or not path.exists():
            result_text.value = "لا يوجد ملف جاهز للحفظ."
            page.update()
            return
        try:
            file_bytes = await asyncio.to_thread(path.read_bytes)
            destination = await file_picker.save_file(
                dialog_title="حفظ الملف",
                file_name=path.name,
                src_bytes=file_bytes,
            )
            result_text.value = "✅ تم حفظ الملف بنجاح." if destination else "تم إلغاء الحفظ."
        except Exception as ex:
            result_text.value = f"❌ تعذر حفظ الملف: {ex}"
        page.update()

    download_button.on_click = start_download
    save_button.on_click = save_file

    def mode_changed(_):
        if mode.value == "audio":
            quality.options = [ft.DropdownOption(key="best", text="أفضل جودة صوت")]
        else:
            quality.options = [
                ft.DropdownOption(key="best", text="أفضل جودة متاحة"),
                ft.DropdownOption(key="1080", text="1080p"),
                ft.DropdownOption(key="720", text="720p"),
                ft.DropdownOption(key="480", text="480p"),
                ft.DropdownOption(key="360", text="360p"),
            ]
        quality.value = "best"
        page.update()

    mode.on_change = mode_changed

    page.add(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Text("🎬", size=46, text_align=ft.TextAlign.CENTER),
                    ft.Text(APP_NAME, size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        "تنزيل الوسائط من الروابط العامة",
                        color="#94a3b8",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Row([url_field, analyze_button]),
                    status,
                    info_card,
                    ft.Row([mode, quality], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([download_button, save_button], alignment=ft.MainAxisAlignment.CENTER),
                    progress,
                    result_text,
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    )


if __name__ == "__main__":
    ft.run(main)
