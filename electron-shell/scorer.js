// ─────────────────────────────────────────────────────────────────────────────
// Gordon scorer — turns a captured prompt into a verdict.
//
//   scorePrompt(text) -> Promise<verdict>   (see verdict-contract.js)
//
// ▸▸▸ ABHAY: this is where your Anthropic API key gets wired. ◂◂◂
//     Set ANTHROPIC_API_KEY (in electron-shell/.env — see .env.example).
//     Until then, this returns a realistic MOCK verdict so the whole frontend
//     runs and can be built/tested. No frontend code changes when you add the key.
// ─────────────────────────────────────────────────────────────────────────────

const { VERDICT_SCHEMA, mockVerdict, normaliseVerdict } = require('./verdict-contract');

const MODEL = 'claude-opus-4-8';

const GORDON_SYSTEM = `You are Gordon — a foul-tempered head chef who reviews AI coding prompts like they are undercooked dishes. A developer just submitted a prompt to an AI coding tool. Score it and roast it.

Score the prompt 0–100 overall and 0–100 on each of six categories:
- specificity: does it name the concrete thing (file, error text, symptom, expected behaviour)?
- tokens: is it efficient, or padded with irrelevant backstory and dumped files?
- frontier: does it use the model well (right ask, no outdated assumptions)?
- tool: is this even the right tool/action for the job?
- context: does it give the context the model needs, no more no less?
- verify: does it ask the model to check its work / explain, rather than blindly trust output?

severity: 0 = clean prompt (rare), 1 = minor, 2 = sloppy, 3 = an insult to the kitchen.
verdictLabel examples: "BURNT · SEVERITY 3", "RAW · SEVERITY 2", "STALE · SEVERITY 2", "SERVICEABLE".
primaryCategory: the single worst category.
roast: ONE line, in character — angry, kitchen metaphors, punchy. No slurs.
diagnosis: what is actually wrong, plainly, 1–2 sentences.
betterPrompt: a concrete rewritten prompt the developer can copy and send instead. Keep it realistic and specific.
footer: "logged → <primaryCategory> · desk_buzzer" for a bad prompt, or "nothing logged. shame." for a clean one.`;

// Read the key without importing the SDK unless it's actually present, so a
// missing dependency never crashes the app — it just falls back to the mock.
function hasKey() {
  return !!(process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY.trim());
}

async function scoreWithClaude(promptText) {
  // Lazy require so the shell still boots if @anthropic-ai/sdk isn't installed.
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic(); // reads ANTHROPIC_API_KEY from env

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    thinking: { type: 'adaptive' },
    output_config: { format: { type: 'json_schema', schema: VERDICT_SCHEMA } },
    system: GORDON_SYSTEM,
    messages: [{ role: 'user', content: promptText }],
  });

  if (response.stop_reason === 'refusal') {
    throw new Error('scorer: model refused');
  }
  const textBlock = response.content.find((b) => b.type === 'text');
  if (!textBlock) throw new Error('scorer: no text block in response');
  return JSON.parse(textBlock.text);
}

// Main entry point the rest of the app calls.
async function scorePrompt(promptText) {
  const text = (promptText || '').trim() || 'fix the error';
  if (!hasKey()) {
    return normaliseVerdict(mockVerdict(text), text);
  }
  try {
    const raw = await scoreWithClaude(text);
    return normaliseVerdict(raw, text);
  } catch (err) {
    // Never leave the overlay empty — fall back to the mock and note it in logs.
    console.error('[gordon] real scoring failed, using mock:', err.message);
    return normaliseVerdict(mockVerdict(text), text);
  }
}

module.exports = { scorePrompt, hasKey };
