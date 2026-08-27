import unittest

from tactical_challenge import GyazoUploadError, parse_gyazo_upload_response


class ParseGyazoUploadResponseTest(unittest.TestCase):
    def test_parses_uploaded_image_information(self):
        response = {
            "image_id": "0123456789abcdef",
            "permalink_url": "https://gyazo.com/0123456789abcdef",
            "url": "https://i.gyazo.com/0123456789abcdef.png",
            "type": "png",
        }

        uploaded = parse_gyazo_upload_response(response)

        self.assertEqual(uploaded.image_id, "0123456789abcdef")
        self.assertEqual(
            uploaded.permalink_url,
            "https://gyazo.com/0123456789abcdef",
        )
        self.assertEqual(
            uploaded.image_url,
            "https://i.gyazo.com/0123456789abcdef.png",
        )

    def test_rejects_response_without_required_fields(self):
        with self.assertRaisesRegex(GyazoUploadError, "レスポンス"):
            parse_gyazo_upload_response({"image_id": "0123456789abcdef"})

    def test_rejects_non_gyazo_urls(self):
        response = {
            "image_id": "0123456789abcdef",
            "permalink_url": "https://example.com/0123456789abcdef",
            "url": "https://example.com/0123456789abcdef.png",
        }

        with self.assertRaisesRegex(GyazoUploadError, "URL"):
            parse_gyazo_upload_response(response)


if __name__ == "__main__":
    unittest.main()
