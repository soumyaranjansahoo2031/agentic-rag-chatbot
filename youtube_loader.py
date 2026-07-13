from urllib.parse import parse_qs, urlparse

# change
from pytubefix import YouTube 

# from youtube_transcript_api import YouTubeTranscriptApi

def get_youtube_transcript(youtube_url: str) -> dict:
    """
    Fetch English captions from a YouTube video using pytubefix.
    """

    yt = YouTube(youtube_url)

    caption = (
        yt.captions.get_by_language_code("en")
        or yt.captions.get_by_language_code("a.en")
    )

    if caption is None:
        raise ValueError(
            "No English or auto-generated English captions were found."
        )

    transcript_text = caption.generate_srt_captions()

    return {
        "video_id": yt.video_id,
        "text": transcript_text,
        "segments": transcript_text.count("\n\n"),
        "title": yt.title,
        "author": yt.author,
    }
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