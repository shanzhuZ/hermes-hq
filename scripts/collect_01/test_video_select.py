# -*- coding: utf-8 -*-
"""video_select：禁止把静态配图当视频。"""
from __future__ import annotations

import json
import unittest

from collect_01.video_select import (
    extract_video_url_from_post,
    _is_image_url,
    _is_video_like_url,
)


class VideoSelectTest(unittest.TestCase):
    def test_image_url_not_video_like(self):
        jpg = "https://pbs.twimg.com/media/HWjLhOUWcAAmmPi.jpg"
        self.assertTrue(_is_image_url(jpg))
        self.assertFalse(_is_video_like_url(jpg))
        self.assertTrue(
            _is_video_like_url("https://video.twimg.com/ext_tw_video/x/pu/vid/720x1280/a.mp4")
        )

    def test_twitter_photo_post_not_selected(self):
        row = {
            "platform": "twitter",
            "account_id": "elonmusk",
            "content_id": "2119406258902224899",
            "content_type": "post",
            "content_url": "https://twitter.com/i/status/2119406258902224899",
            "content_text": "RT @ApoStructura: launch chart",
            "raw_json": json.dumps(
                {
                    "id": "2119406258902224899",
                    "media": [
                        {
                            "url": "https://pbs.twimg.com/media/HWjLhOUWcAAmmPi.jpg",
                            "type": "photo",
                        }
                    ],
                    "media_urls": ["https://pbs.twimg.com/media/HWjLhOUWcAAmmPi.jpg"],
                },
                ensure_ascii=False,
            ),
        }
        self.assertIsNone(extract_video_url_from_post(row))

    def test_twitter_video_post_uses_status_page(self):
        row = {
            "platform": "twitter",
            "account_id": "elonmusk",
            "content_id": "2119114815931039992",
            "content_type": "post",
            "content_url": "https://twitter.com/i/status/2119114815931039992",
            "content_text": "Starship flight maneuvers",
            "raw_json": {
                "id": "2119114815931039992",
                "has_video": True,
                "media_types": ["video"],
                "media": [
                    {
                        "type": "video",
                        "url": "https://video.twimg.com/ext_tw_video/x/pu/vid/720x1280/a.mp4",
                    }
                ],
            },
        }
        self.assertEqual(
            "https://twitter.com/i/status/2119114815931039992",
            extract_video_url_from_post(row),
        )

    def test_youtube_link_in_text_still_works(self):
        row = {
            "platform": "twitter",
            "content_id": "1",
            "content_text": "see https://www.youtube.com/watch?v=6qN5cASYuGo",
            "raw_json": {"media": [{"type": "photo", "url": "https://pbs.twimg.com/media/x.jpg"}]},
        }
        self.assertEqual(
            "https://www.youtube.com/watch?v=6qN5cASYuGo",
            extract_video_url_from_post(row),
        )


if __name__ == "__main__":
    unittest.main()
