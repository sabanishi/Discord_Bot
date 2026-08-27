import unittest


def assert_image_bytes(test_case: unittest.TestCase, image: bytes) -> None:
    """取得データが対応画像形式の実データであることを確認する。"""
    signatures = (
        image.startswith(b"\x89PNG\r\n\x1a\n"),
        image.startswith(b"\xff\xd8\xff"),
        image.startswith((b"GIF87a", b"GIF89a")),
        len(image) >= 12 and image[:4] == b"RIFF" and image[8:12] == b"WEBP",
    )
    test_case.assertTrue(any(signatures), "取得データが対応画像形式ではありません")
