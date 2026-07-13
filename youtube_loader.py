from urllib.parse import parse_qs, urlparse

from pytubefix import YouTube

import logging

logger = logging.getLogger(__name__)


def get_youtube_transcript(youtube_url: str) -> dict:
    logger.info("YouTube loader started")
    logger.info("Video url: %s", youtube_url)
    # print("extracting...")
    logger.info("Attempting to captions")

    yt = YouTube(youtube_url)
    
    available_captions = list(yt.captions)
    logger.info("captions")
    logger.info(available_captions)

    print(
        "AVAILABLE CAPTIONS:",
        [(caption.code, caption.name) for caption in available_captions],
    )

    if not available_captions:
        raise ValueError(
            "No caption tracks were returned by YouTube. "
            "The Streamlit Cloud IP may be blocked."
        )

    caption = None

    # Prefer any English caption, including auto-generated variants.
    for item in available_captions:
        code = item.code.lower()

        if code == "en" or code == "a.en":
            caption = item
            break

    # Then accept other English variants such as en-US or a.en-US.
    if caption is None:
        for item in available_captions:
            code = item.code.lower()

            if code.startswith("en") or code.startswith("a.en"):
                caption = item
                break

    if caption is None:
        available_codes = [
            item.code for item in available_captions
        ]

        raise ValueError(
            "No English caption track was found. "
            f"Available captions: {available_codes}"
        )

    transcript_text = caption.generate_srt_captions()

    return {
        "video_id": yt.video_id,
        "text": transcript_text,
        "segments": transcript_text.count("\n\n"),
        "title": yt.title,
        "author": yt.author,
    }

# from youtube_transcript_api import YouTubeTranscriptApi

# def extract_youtube_video_id(youtube_url: str) -> str:
#     if not youtube_url or not youtube_url.strip():
#         raise ValueError("YouTube URL is required.")

#     parsed_url = urlparse(youtube_url.strip())
#     hostname = (parsed_url.hostname or "").lower()

#     if hostname in {"youtu.be", "www.youtu.be"}:
#         video_id = parsed_url.path.strip("/").split("/")[0]

#     elif "youtube.com" in hostname:
#         if parsed_url.path == "/watch":
#             video_id = parse_qs(parsed_url.query).get("v", [None])[0]

#         elif parsed_url.path.startswith("/shorts/"):
#             video_id = parsed_url.path.split("/")[2]

#         elif parsed_url.path.startswith("/embed/"):
#             video_id = parsed_url.path.split("/")[2]

#         else:
#             video_id = None

#     else:
#         video_id = None

#     if not video_id:
#         raise ValueError("Invalid YouTube URL.")

#     return video_id


# def get_youtube_transcript(youtube_url: str) -> dict:
#     video_id = extract_youtube_video_id(youtube_url)

#     transcript = YouTubeTranscriptApi().fetch(
#         video_id,
#         languages=["en", "hi"],
#     )

#     transcript_text = " ".join(
#         item.text.strip()
#         for item in transcript
#         if item.text.strip()
#     )

#     if not transcript_text:
#         raise ValueError("Transcript is empty.")

#     return {
#         "video_id": video_id,
#         "text": transcript_text,
#         "segments": len(transcript),
#     }