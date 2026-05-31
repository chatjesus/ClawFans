import os, asyncio, time
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"

from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()
text = "你好呀，今天天气真好，想不想一起出去走走？"

t0 = time.time()
response = client.synthesize_speech(
    input=texttospeech.SynthesisInput(text=text),
    voice=texttospeech.VoiceSelectionParams(
        language_code="cmn-CN",
        name="cmn-CN-Chirp3-HD-Kore",
    ),
    audio_config=texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    ),
)
t1 = time.time()

fname = "test_tts.mp3"
with open(fname, "wb") as f:
    f.write(response.audio_content)

print(f"OK! {len(response.audio_content)} bytes in {t1-t0:.2f}s saved to {fname}")
