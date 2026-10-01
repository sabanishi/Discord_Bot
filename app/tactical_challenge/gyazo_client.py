from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp


GYAZO_UPLOAD_URL = "https://upload.gyazo.com/api/upload"


class GyazoUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class GyazoUpload:
    """Gyazoへアップロードした画像の識別子とURL。"""

    image_id: str
    permalink_url: str
    image_url: str


def parse_gyazo_upload_response(response: object) -> GyazoUpload:
    """Gyazoのアップロードレスポンスを検証して画像情報へ変換する。"""
    if not isinstance(response, dict):
        raise GyazoUploadError("Gyazoのレスポンス形式が不正です")

    image_id = response.get("image_id")
    permalink_url = response.get("permalink_url")
    image_url = response.get("url")
    if not all(isinstance(value, str) and value for value in (
        image_id,
        permalink_url,
        image_url,
    )):
        raise GyazoUploadError("Gyazoのレスポンスに必須項目がありません")

    permalink = urlparse(permalink_url)
    image = urlparse(image_url)
    if (
        permalink.scheme != "https"
        or permalink.hostname != "gyazo.com"
        or image.scheme != "https"
        or image.hostname != "i.gyazo.com"
    ):
        raise GyazoUploadError("Gyazoのレスポンスに不正なURLがあります")

    return GyazoUpload(
        image_id=image_id,
        permalink_url=permalink_url,
        image_url=image_url,
    )


class GyazoClient:
    def __init__(self, access_token: str, timeout_seconds: int = 30, session: aiohttp.ClientSession | None = None):
        self.access_token = access_token.strip()
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session = session

    async def upload_image(self, image: bytes, filename: str) -> GyazoUpload:
        """画像を公開設定でGyazoへアップロードする。"""
        if not self.access_token:
            raise ValueError("Gyazoのアクセストークンが必要です")
        if not image:
            raise ValueError("アップロードする画像が空です")
        if not filename.strip():
            raise ValueError("アップロードする画像のファイル名が必要です")

        form = aiohttp.FormData()
        form.add_field(
            "imagedata",
            image,
            filename=filename,
            content_type="image/png",
        )
        form.add_field("access_policy", "anyone")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        session_context = (
            _ExistingSessionContext(self.session)
            if self.session is not None
            else aiohttp.ClientSession(timeout=self.timeout)
        )
        async with session_context as session:
            async with session.post(
                GYAZO_UPLOAD_URL,
                headers=headers,
                data=form,
            ) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise GyazoUploadError(
                        "Gyazoへの画像アップロードに失敗しました: "
                        f"status={response.status}, body={response_text[:500]}"
                    )
                try:
                    response_data = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as exc:
                    raise GyazoUploadError(
                        "Gyazoが不正なJSONを返しました"
                    ) from exc

        return parse_gyazo_upload_response(response_data)


class _ExistingSessionContext:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args: object):
        return None
