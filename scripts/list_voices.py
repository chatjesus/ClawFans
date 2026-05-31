import os
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"

from google.cloud import texttospeech
client = texttospeech.TextToSpeechClient()

voices = client.list_voices(language_code="cmn-CN")
print(f"Found {len(voices.voices)} cmn-CN voices:\n")
for v in voices.voices:
    gender = "FEMALE" if v.ssml_gender == 2 else "MALE" if v.ssml_gender == 1 else str(v.ssml_gender)
    print(f"  {v.name:45s} gender={gender}")
