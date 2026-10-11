"""Playlist management tools."""

from youtube_mcp.server import auth, mcp, quota
from youtube_mcp.utils.localizations import merge_localizations


@mcp.tool()
def youtube_list_playlists(
    channel_id: str | None = None,
    mine: bool = False,
    max_results: int = 25,
) -> dict:
    """List playlists for a channel.

    Args:
        channel_id: Channel ID to list playlists from
        mine: If True, list the authenticated user's playlists
        max_results: Number of playlists to return. Values above 50 are
            served by paging through results; pass 0 or a negative value to
            fetch every playlist.
    """
    youtube = auth.build_youtube_service()
    target = max_results if (max_results and max_results > 0) else None

    base_params = {"part": "snippet,contentDetails,status,localizations"}
    if mine:
        base_params["mine"] = True
    elif channel_id:
        base_params["channelId"] = channel_id
    else:
        return {"error": "Provide channel_id or set mine=True"}

    playlists = []
    page_token = None
    response = {}
    while True:
        page_size = 50 if target is None else min(50, target - len(playlists))
        if page_size <= 0:
            break
        quota.consume("list")
        response = (
            youtube.playlists()
            .list(**base_params, maxResults=page_size, pageToken=page_token)
            .execute()
        )
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            playlists.append({
                "id": item["id"],
                "title": snippet.get("title"),
                "description": snippet.get("description", ""),
                "published_at": snippet.get("publishedAt"),
                "privacy": item.get("status", {}).get("privacyStatus"),
                "video_count": item.get("contentDetails", {}).get("itemCount", 0),
                "default_language": snippet.get("defaultLanguage"),
                "localizations": item.get("localizations", {}),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url"),
            })
        page_token = response.get("nextPageToken")
        if not page_token:
            break
        if target is not None and len(playlists) >= target:
            break

    total = response.get("pageInfo", {}).get("totalResults", len(playlists))
    return {"playlists": playlists, "total": total}


@mcp.tool()
def youtube_create_playlist(
    title: str,
    description: str = "",
    privacy_status: str = "private",
) -> dict:
    """Create a new playlist.

    Args:
        title: Playlist title
        description: Playlist description
        privacy_status: "private", "public", or "unlisted"
    """
    quota.consume("insert")
    youtube = auth.build_youtube_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    response = youtube.playlists().insert(part="snippet,status", body=body).execute()

    return {
        "id": response["id"],
        "title": response["snippet"]["title"],
        "privacy": response["status"]["privacyStatus"],
        "url": f"https://www.youtube.com/playlist?list={response['id']}",
    }


@mcp.tool()
def youtube_update_playlist(
    playlist_id: str,
    title: str | None = None,
    description: str | None = None,
    privacy_status: str | None = None,
    localizations: dict[str, dict[str, str]] | None = None,
    default_language: str | None = None,
) -> dict:
    """Update metadata for an existing playlist.

    Only provided fields are updated; others remain unchanged.

    Args:
        playlist_id: Playlist ID to update
        title: New title
        description: New description
        privacy_status: "private", "public", or "unlisted"
        localizations: Translated title/description per language, e.g.
            {"uk": {"title": "...", "description": "..."}}. Merged into the
            existing translations: other languages and fields not passed stay.
            A new language needs a title.
        default_language: Language of the main title/description
            (snippet.defaultLanguage, e.g. "ru"). Required when adding
            localizations to a playlist that has none set.
    """
    quota.consume("list")
    youtube = auth.build_youtube_service()

    current = (
        youtube.playlists().list(part="snippet,status,localizations", id=playlist_id).execute()
    )
    items = current.get("items", [])
    if not items:
        return {"error": f"Playlist not found: {playlist_id}"}

    playlist = items[0]
    snippet = playlist["snippet"]
    status = playlist.get("status", {})

    if title is not None:
        snippet["title"] = title
    if description is not None:
        snippet["description"] = description

    # playlists.update ersetzt den kompletten localizations-Part: zusammenfuehren.
    new_localizations, error = merge_localizations(
        snippet, playlist.get("localizations"), localizations, default_language, title_limit=150
    )
    if error:
        return {"error": error}

    body = {"id": playlist_id, "snippet": snippet}

    if privacy_status is not None:
        body["status"] = {"privacyStatus": privacy_status}
        parts = "snippet,status"
    else:
        parts = "snippet"

    if new_localizations is not None:
        body["localizations"] = new_localizations
        parts += ",localizations"

    quota.consume("update")
    response = youtube.playlists().update(part=parts, body=body).execute()

    response_status = response.get("status") or {}
    return {
        "id": response["id"],
        "title": response["snippet"]["title"],
        "privacy": response_status.get("privacyStatus"),
        "default_language": response["snippet"].get("defaultLanguage"),
        "localizations": response.get("localizations"),
        "updated": True,
    }


@mcp.tool()
def youtube_list_playlist_items(playlist_id: str, max_results: int = 0) -> dict:
    """List the videos in a playlist, in playlist order.

    Args:
        playlist_id: Playlist ID
        max_results: Number of items to return; 0 or negative fetches all
            (pages of 50, 1 quota unit per page).

    Returns the playlist_item_id needed by youtube_move_playlist_item and
    youtube_remove_from_playlist.
    """
    youtube = auth.build_youtube_service()
    target = max_results if (max_results and max_results > 0) else None

    items = []
    page_token = None
    response = {}
    while True:
        page_size = 50 if target is None else min(50, target - len(items))
        if page_size <= 0:
            break
        quota.consume("list")
        response = (
            youtube.playlistItems()
            .list(
                part="snippet,contentDetails,status",
                playlistId=playlist_id,
                maxResults=page_size,
                pageToken=page_token,
            )
            .execute()
        )
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            items.append({
                "playlist_item_id": item["id"],
                "video_id": item.get("contentDetails", {}).get("videoId")
                or snippet.get("resourceId", {}).get("videoId"),
                "title": snippet.get("title"),
                "position": snippet.get("position"),
                "privacy": item.get("status", {}).get("privacyStatus"),
            })
        page_token = response.get("nextPageToken")
        if not page_token:
            break
        if target is not None and len(items) >= target:
            break

    total = response.get("pageInfo", {}).get("totalResults", len(items))
    return {"playlist_id": playlist_id, "items": items, "total": total}


@mcp.tool()
def youtube_move_playlist_item(
    playlist_item_id: str,
    playlist_id: str,
    video_id: str,
    position: int,
) -> dict:
    """Move a video to another position inside a playlist.

    Get playlist_item_id and video_id from youtube_list_playlist_items.

    Args:
        playlist_item_id: The playlist item ID (not the video ID)
        playlist_id: Playlist the item belongs to
        video_id: Video ID of that item
        position: New position (0-based)
    """
    if position < 0:
        return {"error": "position must be 0 or greater"}

    quota.consume("update")
    youtube = auth.build_youtube_service()

    body = {
        "id": playlist_item_id,
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
            "position": position,
        },
    }
    response = youtube.playlistItems().update(part="snippet", body=body).execute()

    return {
        "playlist_item_id": response["id"],
        "playlist_id": playlist_id,
        "video_id": video_id,
        "position": response["snippet"].get("position"),
        "moved": True,
    }


@mcp.tool()
def youtube_delete_playlist(playlist_id: str) -> dict:
    """Delete a playlist. This action is irreversible and does not delete the
    videos in it, only the playlist itself.

    Args:
        playlist_id: Playlist ID to delete
    """
    quota.consume("delete")
    youtube = auth.build_youtube_service()

    youtube.playlists().delete(id=playlist_id).execute()

    return {"playlist_id": playlist_id, "deleted": True}


@mcp.tool()
def youtube_add_to_playlist(playlist_id: str, video_id: str, position: int | None = None) -> dict:
    """Add a video to a playlist.

    Args:
        playlist_id: Playlist ID to add the video to
        video_id: Video ID to add
        position: Position in the playlist (0-based). Defaults to end.
    """
    quota.consume("insert")
    youtube = auth.build_youtube_service()

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
        },
    }
    if position is not None:
        body["snippet"]["position"] = position

    response = youtube.playlistItems().insert(part="snippet", body=body).execute()

    return {
        "playlist_item_id": response["id"],
        "playlist_id": playlist_id,
        "video_id": video_id,
        "position": response["snippet"].get("position"),
        "added": True,
    }


@mcp.tool()
def youtube_remove_from_playlist(playlist_item_id: str) -> dict:
    """Remove a video from a playlist.

    Use youtube_list_playlists or the Data API to find the playlist_item_id.

    Args:
        playlist_item_id: The playlist item ID (not the video ID)
    """
    quota.consume("delete")
    youtube = auth.build_youtube_service()

    youtube.playlistItems().delete(id=playlist_item_id).execute()

    return {"playlist_item_id": playlist_item_id, "removed": True}
