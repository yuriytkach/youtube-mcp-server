"""Tests for localizations (videos/playlists) and playlist item tools, mocked API."""

from unittest.mock import MagicMock, patch


def _video(localizations=None, default_language="ru"):
    snippet = {"title": "T", "description": "D", "tags": ["a"], "categoryId": "27"}
    if default_language:
        snippet["defaultLanguage"] = default_language
    video = {"id": "vid1", "snippet": snippet, "status": {"privacyStatus": "public"}}
    if localizations is not None:
        video["localizations"] = localizations
    return {"items": [video]}


def _update_call(mock_yt_resource):
    """Last kwargs passed to <resource>().update(...)."""
    return mock_yt_resource().update.call_args.kwargs


class TestUpdateVideoLocalizations:
    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_merges_with_existing_languages(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video(
            {"en": {"title": "EN", "description": "en d"},
             "uk": {"title": "UK old", "description": "uk d"}}
        )
        mock_yt.videos().update().execute.return_value = {"id": "vid1", "snippet": {"title": "T"}}

        result = youtube_update_video(video_id="vid1", localizations={"uk": {"title": "UK new"}})

        assert "error" not in result
        kwargs = _update_call(mock_yt.videos)
        assert kwargs["part"] == "snippet,localizations"
        body = kwargs["body"]
        assert body["localizations"] == {
            "en": {"title": "EN", "description": "en d"},
            "uk": {"title": "UK new", "description": "uk d"},
        }
        # main snippet untouched
        assert body["snippet"]["title"] == "T"
        assert body["snippet"]["tags"] == ["a"]
        assert body["snippet"]["categoryId"] == "27"
        assert "status" not in body

    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_requires_default_language(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video(default_language=None)

        result = youtube_update_video(video_id="vid1", localizations={"uk": {"title": "X"}})
        assert "default_language" in result["error"]
        mock_yt.videos().update.assert_not_called()

    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_sets_default_language_when_passed(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video(default_language=None)
        mock_yt.videos().update().execute.return_value = {"id": "vid1", "snippet": {"title": "T"}}

        youtube_update_video(
            video_id="vid1", default_language="ru",
            localizations={"uk": {"title": "X", "description": "Y"}},
        )
        body = _update_call(mock_yt.videos)["body"]
        assert body["snippet"]["defaultLanguage"] == "ru"
        assert body["localizations"] == {"uk": {"title": "X", "description": "Y"}}

    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_new_language_needs_title(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video({})

        result = youtube_update_video(video_id="vid1", localizations={"uk": {"description": "Y"}})
        assert "needs a title" in result["error"]

    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_rejects_default_language_as_translation(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video({})

        result = youtube_update_video(video_id="vid1", localizations={"ru": {"title": "Y"}})
        assert "default language" in result["error"]

    @patch("youtube_mcp.tools.publishing.auth")
    @patch("youtube_mcp.tools.publishing.quota")
    def test_without_localizations_part_not_sent(self, mock_quota, mock_auth):
        from youtube_mcp.tools.publishing import youtube_update_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video({"uk": {"title": "U"}})
        mock_yt.videos().update().execute.return_value = {"id": "vid1", "snippet": {"title": "N"}}

        youtube_update_video(video_id="vid1", title="N")
        kwargs = _update_call(mock_yt.videos)
        assert kwargs["part"] == "snippet"
        assert "localizations" not in kwargs["body"]


class TestGetVideoLocalizations:
    @patch("youtube_mcp.tools.channel.auth")
    @patch("youtube_mcp.tools.channel.quota")
    def test_returns_localizations(self, mock_quota, mock_auth):
        from youtube_mcp.tools.channel import youtube_get_video

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.videos().list().execute.return_value = _video({"uk": {"title": "U"}})

        result = youtube_get_video("vid1")
        assert result["default_language"] == "ru"
        assert result["localizations"] == {"uk": {"title": "U"}}
        assert "localizations" in mock_yt.videos().list.call_args.kwargs["part"]


class TestPlaylistLocalizations:
    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_merge_keeps_snippet_and_languages(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_update_playlist

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.playlists().list().execute.return_value = {"items": [{
            "id": "PL1",
            "snippet": {"title": "P", "description": "PD", "defaultLanguage": "ru"},
            "status": {"privacyStatus": "public"},
            "localizations": {"en": {"title": "PE"}},
        }]}
        mock_yt.playlists().update().execute.return_value = {"id": "PL1", "snippet": {"title": "P"}}

        result = youtube_update_playlist(
            playlist_id="PL1", localizations={"uk": {"title": "PU", "description": "PUD"}}
        )
        assert "error" not in result
        kwargs = _update_call(mock_yt.playlists)
        assert kwargs["part"] == "snippet,localizations"
        assert kwargs["body"]["snippet"]["description"] == "PD"
        assert kwargs["body"]["localizations"] == {
            "en": {"title": "PE"},
            "uk": {"title": "PU", "description": "PUD"},
        }

    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_requires_default_language(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_update_playlist

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.playlists().list().execute.return_value = {"items": [{
            "id": "PL1", "snippet": {"title": "P"}, "status": {},
        }]}
        result = youtube_update_playlist(playlist_id="PL1", localizations={"uk": {"title": "X"}})
        assert "default_language" in result["error"]

    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_list_has_privacy_and_full_description(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_list_playlists

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        long_desc = "x" * 900
        mock_yt.playlists().list().execute.return_value = {"items": [{
            "id": "PL1",
            "snippet": {"title": "P", "description": long_desc},
            "status": {"privacyStatus": "unlisted"},
            "contentDetails": {"itemCount": 3},
        }]}
        result = youtube_list_playlists(mine=True)
        pl = result["playlists"][0]
        assert pl["privacy"] == "unlisted"
        assert pl["description"] == long_desc


class TestPlaylistItems:
    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_list_items_pages(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_list_playlist_items

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt

        def item(i):
            return {
                "id": f"PI{i}",
                "snippet": {"title": f"V{i}", "position": i,
                            "resourceId": {"videoId": f"v{i}"}},
                "contentDetails": {"videoId": f"v{i}"},
                "status": {"privacyStatus": "public"},
            }

        pages = [
            {"items": [item(i) for i in range(50)], "nextPageToken": "t2",
             "pageInfo": {"totalResults": 60}},
            {"items": [item(i) for i in range(50, 60)], "pageInfo": {"totalResults": 60}},
        ]
        mock_yt.playlistItems().list.side_effect = None
        mock_yt.playlistItems().list.return_value.execute.side_effect = pages

        result = youtube_list_playlist_items("PL1")
        assert result["total"] == 60
        assert len(result["items"]) == 60
        assert result["items"][59] == {
            "playlist_item_id": "PI59", "video_id": "v59", "title": "V59",
            "position": 59, "privacy": "public",
        }
        last_kwargs = mock_yt.playlistItems().list.call_args.kwargs
        assert last_kwargs["pageToken"] == "t2"
        assert last_kwargs["playlistId"] == "PL1"

    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_move_item(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_move_playlist_item

        mock_yt = MagicMock()
        mock_auth.build_youtube_service.return_value = mock_yt
        mock_yt.playlistItems().update().execute.return_value = {
            "id": "PI1", "snippet": {"position": 0},
        }

        result = youtube_move_playlist_item("PI1", "PL1", "v1", 0)
        assert result["moved"] is True and result["position"] == 0
        kwargs = _update_call(mock_yt.playlistItems)
        assert kwargs["part"] == "snippet"
        assert kwargs["body"] == {
            "id": "PI1",
            "snippet": {"playlistId": "PL1",
                        "resourceId": {"kind": "youtube#video", "videoId": "v1"},
                        "position": 0},
        }

    @patch("youtube_mcp.tools.playlists.auth")
    @patch("youtube_mcp.tools.playlists.quota")
    def test_move_negative_position(self, mock_quota, mock_auth):
        from youtube_mcp.tools.playlists import youtube_move_playlist_item

        result = youtube_move_playlist_item("PI1", "PL1", "v1", -1)
        assert "error" in result
