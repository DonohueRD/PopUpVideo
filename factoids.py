import json
import re
import anthropic

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """\
You are the writer for a VH1 Pop Up Video revival called Huey Pop Up Video.
Generate fun, surprising, slightly irreverent factoids in the style of the original show.
Rules:
- 1 to 3 sentences per bubble. Punchy. Factual.
- Vary categories: chart performance, recording history, artist personal details, \
music video production, trivia, cultural impact.
- No emojis. No markdown.
- Return ONLY a valid JSON array of objects with "text" (string) and "category" (string) fields.
- Generate exactly 8 to 10 factoids."""


class FactoidParseError(Exception):
    pass


def parse_factoid_response(raw: str) -> list[dict]:
    """Parse a Claude response into a list of factoid dicts."""
    # Strip markdown code fences
    text = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise FactoidParseError(f"Invalid JSON: {e}") from e

    if not isinstance(data, list) or len(data) == 0:
        raise FactoidParseError("Response must be a non-empty JSON array")

    for item in data:
        if not isinstance(item, dict) or "text" not in item:
            raise FactoidParseError(f"Each item must have a 'text' key; got: {item}")

    return data


def generate_factoids(artist: str, song_title: str) -> list[dict]:
    """Call Claude API to generate VH1-style pop-up video factoids."""
    client = anthropic.Anthropic()
    prompt = (
        f"Generate 8-10 pop-up video factoids for '{song_title}' by {artist}. "
        "Return a JSON array of objects with 'text' and 'category' fields. "
        "Categories: chart, recording, artist, production, trivia, cultural."
    )

    for attempt in range(2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        try:
            return parse_factoid_response(raw)
        except FactoidParseError:
            if attempt == 1:
                raise
    # unreachable
    raise FactoidParseError("Unexpected exit")
