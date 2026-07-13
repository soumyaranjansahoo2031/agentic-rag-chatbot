# from urllib.parse import parse_qs, urlparse

# from pytubefix import YouTube

# import logging

# logger = logging.getLogger(__name__)


# def get_youtube_transcript(youtube_url: str) -> dict:


#     logger.info("YouTube loader started")
#     logger.info("Video url: %s", youtube_url)
#     # print("extracting...")
#     logger.info("Attempting to captions")
#     logger.info("...")

#     yt = YouTube(youtube_url)

#     logger.info("Checkpoint : YouTube object created")

#     captions_object = yt.captions

#     logger.info("Checkpoint 4: yt.captions accessed")

#     available_captions = list(captions_object)
#     logger.info("captions")
#     logger.info(available_captions)

#     print(
#         "AVAILABLE CAPTIONS:",
#         [(caption.code, caption.name) for caption in available_captions],
#     )

#     if not available_captions:
#         raise ValueError(
#             "No caption tracks were returned by YouTube. "
#             "The Streamlit Cloud IP may be blocked."
#         )

#     caption = None

#     # Prefer any English caption, including auto-generated variants.
#     for item in available_captions:
#         code = item.code.lower()

#         if code == "en" or code == "a.en":
#             caption = item
#             break

#     # Then accept other English variants such as en-US or a.en-US.
#     if caption is None:
#         for item in available_captions:
#             code = item.code.lower()

#             if code.startswith("en") or code.startswith("a.en"):
#                 caption = item
#                 break

#     if caption is None:
#         available_codes = [
#             item.code for item in available_captions
#         ]

#         raise ValueError(
#             "No English caption track was found. "
#             f"Available captions: {available_codes}"
#         )

#     transcript_text = caption.generate_srt_captions()

#     return {
#         "video_id": yt.video_id,
#         "text": transcript_text,
#         "segments": transcript_text.count("\n\n"),
#         "title": yt.title,
#         "author": yt.author,
#     }
import logging
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger("youtube_loader")


def extract_youtube_video_id(youtube_url: str) -> str:
    logger.info("===== Extracting YouTube Video ID =====")
    logger.info("Input URL: %s", youtube_url)

    if not youtube_url or not youtube_url.strip():
        logger.error("YouTube URL is empty.")
        raise ValueError("YouTube URL is required.")

    parsed_url = urlparse(youtube_url.strip())
    hostname = (parsed_url.hostname or "").lower()

    logger.info("Parsed hostname: %s", hostname)
    logger.info("Parsed path: %s", parsed_url.path)

    if hostname in {"youtu.be", "www.youtu.be"}:
        logger.info("Detected short YouTube URL.")
        video_id = parsed_url.path.strip("/").split("/")[0]

    elif "youtube.com" in hostname:
        logger.info("Detected standard YouTube URL.")

        if parsed_url.path == "/watch":
            logger.info("Watch URL detected.")
            video_id = parse_qs(parsed_url.query).get("v", [None])[0]

        elif parsed_url.path.startswith("/shorts/"):
            logger.info("Shorts URL detected.")
            video_id = parsed_url.path.split("/")[2]

        elif parsed_url.path.startswith("/embed/"):
            logger.info("Embed URL detected.")
            video_id = parsed_url.path.split("/")[2]

        else:
            logger.error("Unsupported YouTube URL format.")
            video_id = None

    else:
        logger.error("Invalid hostname.")
        video_id = None

    if not video_id:
        logger.error("Could not extract video ID.")
        raise ValueError("Invalid YouTube URL.")

    logger.info("Extracted Video ID: %s", video_id)

    return video_id


def get_youtube_transcript(youtube_url: str) -> dict:
    logger.info("===== YouTube Transcript Loading Started =====")

    try:
        logger.info("Step 1: Extracting video ID")

        video_id = extract_youtube_video_id(youtube_url)

        logger.info("Step 2: Video ID extracted successfully")
        logger.info("Video ID: %s", video_id)

        logger.info("Step 3: Creating YouTubeTranscriptApi instance")

        api = YouTubeTranscriptApi()

        logger.info("Step 4: Fetching transcript")

        transcript = api.fetch(
            video_id,
            languages=["en", "hi"],
        )

        logger.info("Step 5: Transcript fetched successfully")
        logger.info("Transcript segment count: %s", len(transcript))

        logger.info("Step 6: Joining transcript text")

        transcript_text = " ".join(
            item.text.strip()
            for item in transcript
            if item.text.strip()
        )

        logger.info("Transcript character count: %s", len(transcript_text))

        if not transcript_text:
            logger.error("Transcript is empty.")
            raise ValueError("Transcript is empty.")

        logger.info("===== Transcript Processing Completed =====")

        return {
            "video_id": video_id,
            "text": transcript_text,
            "segments": len(transcript),
        }

    except Exception as error:
        logger.error("===== YouTube Transcript Loading Failed =====")
        logger.error("Error Type: %s", type(error).__name__)
        logger.error("Error Message: %s", str(error))
        logger.exception("Complete traceback")
        raise