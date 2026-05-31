"""
TTS Worker — isolated subprocess for Google Cloud TTS synthesis.
Called by voice_service.py to avoid gRPC/uvicorn event loop conflicts on Windows.

Usage: python _tts_worker.py '{"text":"...","voice_name":"...","rate":1.0,"credentials":"...","output":"..."}'
"""
import sys, os, json

def main():
    args = json.loads(sys.argv[1])
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args["credentials"]

    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=args["text"]),
        voice=texttospeech.VoiceSelectionParams(
            language_code="cmn-CN",
            name=args["voice_name"],
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=args.get("rate", 1.0),
        ),
    )

    with open(args["output"], "wb") as f:
        f.write(response.audio_content)

if __name__ == "__main__":
    main()
