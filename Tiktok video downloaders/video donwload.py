from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL


app = FastAPI(title="TikTok Video Downloader", version="1.0.0")

DEFAULT_TIKTOK_URL = "https://vm.tiktok.com/ZN86hftwp/"
ALLOWED_HOSTS = {
	"tiktok.com",
	"www.tiktok.com",
	"m.tiktok.com",
	"vm.tiktok.com",
	"vt.tiktok.com",
}


class DownloadRequest(BaseModel):
	url: str = Field(default=DEFAULT_TIKTOK_URL, min_length=1)


def validate_tiktok_url(url: str) -> str:
	parsed = urlparse(url)
	hostname = (parsed.hostname or "").lower().rstrip(".")
	if parsed.scheme not in {"http", "https"} or hostname not in ALLOWED_HOSTS:
		raise HTTPException(
			status_code=400,
			detail="Only TikTok URLs are supported.",
		)
	return url


def safe_filename(title: str) -> str:
	cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._")
	return (cleaned or "tiktok_video")[:120] + ".mp4"


def remove_directory(path: str) -> None:
	shutil.rmtree(path, ignore_errors=True)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.get("/title", response_class=PlainTextResponse)
def video_title(url: str = DEFAULT_TIKTOK_URL) -> PlainTextResponse:
	validate_tiktok_url(url)
	try:
		with YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as downloader:
			info = downloader.extract_info(url, download=False)
	except Exception as error:
		raise HTTPException(status_code=502, detail=f"Could not read TikTok title: {error}") from error

	title = str(info.get("title") or "tiktok_video")
	return PlainTextResponse(
		content=title,
		headers={"Content-Disposition": 'attachment; filename="title.txt"'},
	)


@app.post("/download")
def download_video(request: DownloadRequest, background_tasks: BackgroundTasks) -> FileResponse:
	url = validate_tiktok_url(request.url)
	temporary_directory = tempfile.mkdtemp(prefix="tiktok-")
	output_template = os.path.join(temporary_directory, "video.%(ext)s")

	options = {
		"format": "best[ext=mp4]/best",
		"outtmpl": output_template,
		"noplaylist": True,
		"quiet": True,
		"no_warnings": True,
	}

	try:
		with YoutubeDL(options) as downloader:
			info = downloader.extract_info(url, download=True)
			downloaded_path = Path(downloader.prepare_filename(info))
			if downloaded_path.suffix.lower() != ".mp4":
				mp4_path = downloaded_path.with_suffix(".mp4")
				if mp4_path.exists():
					downloaded_path = mp4_path

		if not downloaded_path.exists():
			raise RuntimeError("The downloaded video file was not created.")
	except Exception as error:
		remove_directory(temporary_directory)
		raise HTTPException(status_code=502, detail=f"TikTok download failed: {error}") from error

	background_tasks.add_task(remove_directory, temporary_directory)
	title = str(info.get("title") or "tiktok_video")
	return FileResponse(
		path=downloaded_path,
		media_type="video/mp4",
		filename=safe_filename(title),
		background=background_tasks,
	)


@app.get("/download")
def download_video_get(
	background_tasks: BackgroundTasks,
	url: str = DEFAULT_TIKTOK_URL,
) -> FileResponse:
	return download_video(DownloadRequest(url=url), background_tasks)


if __name__ == "__main__":
	import uvicorn

	uvicorn.run(app, host="127.0.0.1", port=8000)
