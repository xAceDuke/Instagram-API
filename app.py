import base64
import mimetypes
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from flask import Flask, Response, jsonify, send_file
from instaloader import Instaloader, Profile
from instaloader.exceptions import (
    BadCredentialsException,
    ConnectionException,
    ProfileNotExistsException,
    TwoFactorAuthRequiredException,
)

CACHE_TTL_SECONDS = 3 * 60 * 60
IMAGE_CACHE_DIR = Path(os.getenv("IMAGE_CACHE_DIR", "/tmp/instagram-pfp-cache"))

app = Flask(__name__)

cache_lock = threading.Lock()
profile_cache: dict[str, dict] = {}


class InstagramSessionError(RuntimeError):
    pass


def _iso_utc(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _content_type_for_path(file_path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def _download_image(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response:
        destination.write_bytes(response.read())


def _file_extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


def _prepare_session_file_from_b64() -> str | None:
    session_b64 = os.getenv("INSTAGRAM_SESSION_FILE_B64", "").strip()
    if not session_b64:
        return None

    target_path = os.getenv("INSTAGRAM_SESSION_FILE", "/tmp/instagram.session")
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    normalized_b64 = "".join(session_b64.split())
    decoded = base64.b64decode(normalized_b64)
    target.write_bytes(decoded)
    return str(target)


def _load_instaloader_session(loader: Instaloader) -> None:
    login_user = os.getenv("INSTAGRAM_LOGIN_USER", "").strip()
    session_file = os.getenv("INSTAGRAM_SESSION_FILE", "").strip()

    if not login_user:
        raise InstagramSessionError("Missing INSTAGRAM_LOGIN_USER environment variable.")

    if not session_file:
        session_file = "/tmp/instagram.session"

    session_path = Path(session_file)
    if not session_path.exists():
        fallback = _prepare_session_file_from_b64()
        if fallback:
            session_file = fallback
            session_path = Path(session_file)

    if not session_file:
        raise InstagramSessionError(
            "Missing INSTAGRAM_SESSION_FILE (or INSTAGRAM_SESSION_FILE_B64) environment variable."
        )

    if not session_path.exists():
        raise InstagramSessionError(f"Session file not found: {session_file}")

    try:
        loader.load_session_from_file(login_user, filename=session_file)
    except (BadCredentialsException, TwoFactorAuthRequiredException) as exc:
        raise InstagramSessionError(
            "Failed to authenticate with the provided session file."
        ) from exc


def _fetch_pfp(username: str) -> dict:
    normalized = username.strip().lower()
    now = time.time()

    with cache_lock:
        existing = profile_cache.get(normalized)
        if (
            existing
            and existing["expires_at_epoch"] > now
            and Path(existing["local_path"]).exists()
        ):
            return {
                "username": normalized,
                "local_path": existing["local_path"],
                "content_type": existing["content_type"],
                "cached": True,
                "expires_at": _iso_utc(existing["expires_at_epoch"]),
            }

    loader = Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
    )
    _load_instaloader_session(loader)

    try:
        profile = Profile.from_username(loader.context, normalized)
    except ProfileNotExistsException as exc:
        raise ValueError(f"Instagram username does not exist: {normalized}") from exc
    except ConnectionException as exc:
        raise RuntimeError("Instagram connection failed while fetching profile.") from exc

    ext = _file_extension_from_url(profile.profile_pic_url)
    local_path = IMAGE_CACHE_DIR / f"{normalized}{ext}"
    try:
        _download_image(profile.profile_pic_url, local_path)
    except URLError as exc:
        raise RuntimeError("Failed to download profile image from Instagram.") from exc

    content_type = _content_type_for_path(local_path)
    expires = now + CACHE_TTL_SECONDS
    data = {
        "local_path": str(local_path),
        "content_type": content_type,
        "expires_at_epoch": expires,
    }

    with cache_lock:
        profile_cache[normalized] = data

    return {
        "username": normalized,
        "local_path": str(local_path),
        "content_type": content_type,
        "cached": False,
        "expires_at": _iso_utc(expires),
    }


@app.get("/health")
def health() -> tuple:
    return jsonify({"ok": True, "cache_ttl_seconds": CACHE_TTL_SECONDS}), 200


@app.get("/api/pfp/<username>")
def get_profile_pic(username: str):
    if not username.strip():
        return jsonify({"error": "Username is required."}), 400

    try:
        payload = _fetch_pfp(username)
        file_path = Path(payload["local_path"])
        if not file_path.exists():
            return jsonify({"error": "Cached image file not found."}), 500

        response: Response = send_file(file_path, mimetype=payload["content_type"])
        response.headers["X-Cache"] = "HIT" if payload["cached"] else "MISS"
        response.headers["X-Cache-Expires-At"] = payload["expires_at"]
        return response
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except InstagramSessionError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        return jsonify({"error": "Unexpected server error."}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
