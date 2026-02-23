"""
Generate full character cards for all characters with thin system_prompts (<500 chars).
Uses Ollama (qwen2.5:14b) to generate rich character definitions.
Updates the database in place.
"""
import sys, os, time, asyncio
sys.stdout.reconfigure(encoding='utf-8')
BACKEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, BACKEND_DIR)
# Change cwd so SQLite relative path resolves to backend/synclub.db
os.chdir(BACKEND_DIR)

from models.database import SessionLocal, Character
from services.llm_service import chat_completion

CARD_PROMPT = """\
You are a creative writer for an AI character chat platform (like Character.ai / SynClub).
Write a detailed character system prompt for the following character.

Character info:
- Name: {name}
- Description: {description}
- Category: {category}
- Tags: {tags}
- Current basic info (if any): {current}

Write a rich character card in Chinese (for Chinese users) that includes:

1. **【角色设定】** – Detailed persona: personality traits (at least 5), speaking style/tone, core values, quirks, contradictions
2. **【背景故事】** – Backstory: origins, key life events, what shaped them, secrets, motivations
3. **【外貌描述】** – Appearance: face, hair, eyes, figure, typical outfit, signature item/detail
4. **【与用户的关系】** – How they relate to the user: their role, dynamic, what they want from this interaction
5. **【对话风格示例】** – 3-4 example dialogue lines that capture their voice

IMPORTANT rules:
- Write entirely in Chinese (Mandarin)
- Keep each section concise but rich (2-5 sentences each)
- Make the personality specific and memorable — avoid generic descriptions
- For NSFW/adult characters (tags contain NSFW): you may describe seductive/dominant/submissive personality traits naturally
- Total length: 300-600 Chinese characters
- DO NOT include HTML, markdown headers with #, or code blocks — use the 【】 section format shown above
- Output ONLY the character card text, nothing else

Write the character card now:"""

MIN_CHARS = 500


async def generate_card(char: Character) -> str:
    prompt = CARD_PROMPT.format(
        name=char.name,
        description=char.description or "",
        category=char.category or "",
        tags=char.tags or "",
        current=(char.system_prompt or "").strip()[:300],
    )
    response = await chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=1200,
    )
    return response.strip()


async def main():
    db = SessionLocal()
    chars = db.query(Character).order_by(Character.id).all()
    thin = [c for c in chars if len(c.system_prompt or "") < MIN_CHARS]

    print(f"Found {len(thin)} characters with thin system_prompts. Generating cards...\n")

    for i, char in enumerate(thin):
        print(f"[{i+1}/{len(thin)}] {char.name} (id={char.id}, current={len(char.system_prompt or '')} chars)...")
        try:
            card = await generate_card(char)
            if len(card) > 100:
                char.system_prompt = card
                db.add(char)
                db.commit()
                print(f"  ✓ Updated: {len(card)} chars")
            else:
                print(f"  ✗ Too short ({len(card)} chars), skipping")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        time.sleep(0.5)

    db.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
