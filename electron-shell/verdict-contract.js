// ─────────────────────────────────────────────────────────────────────────────
// Gordon verdict contract
//
// This is the single data shape that flows through the whole frontend:
//   capture (teammate)  ->  scorePrompt(text)  ->  verdict  ->  overlay renders it
//
// The overlay renders ONLY from this object. The scorer (real Claude call or the
// mock below) is the only thing that produces it. Keep this shape stable — it's
// the seam the capture + backend teammates plug into.
// ─────────────────────────────────────────────────────────────────────────────

// Six scoring categories, in radar order (matches the design handoff).
const CATEGORY_KEYS = ['specificity', 'tokens', 'frontier', 'tool', 'context', 'verify'];

const CATEGORY_LABELS = {
  specificity: 'SPEC',
  tokens: 'TOKENS',
  frontier: 'FRONTIER',
  tool: 'TOOL',
  context: 'CONTEXT',
  verify: 'VERIFY',
};

// JSON Schema the model is constrained to. Note: JSON-schema numeric ranges
// (minimum/maximum) aren't enforced by structured outputs, so we clamp in code.
const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    score: { type: 'integer', description: 'Overall prompt quality, 0 (BURNT) to 100 (perfect).' },
    severity: { type: 'integer', enum: [0, 1, 2, 3], description: '0 = clean, 3 = worst offence.' },
    verdictLabel: { type: 'string', description: 'e.g. "BURNT · SEVERITY 3", "RAW · SEVERITY 2", "SERVICEABLE".' },
    primaryCategory: { type: 'string', enum: CATEGORY_KEYS, description: 'The single worst category — highlighted.' },
    categories: {
      type: 'object',
      additionalProperties: false,
      properties: {
        specificity: { type: 'integer' },
        tokens: { type: 'integer' },
        frontier: { type: 'integer' },
        tool: { type: 'integer' },
        context: { type: 'integer' },
        verify: { type: 'integer' },
      },
      required: CATEGORY_KEYS,
    },
    roast: { type: 'string', description: "Gordon's one-line roast, in character. Punchy, profane-adjacent, kitchen metaphors." },
    diagnosis: { type: 'string', description: 'What is actually wrong with the prompt, plainly.' },
    betterPrompt: { type: 'string', description: 'A concrete rewritten prompt the user can copy and send instead.' },
    footer: { type: 'string', description: 'e.g. "logged → specificity · desk_buzzer" or "nothing logged. shame." on a clean prompt.' },
  },
  required: ['score', 'severity', 'verdictLabel', 'primaryCategory', 'categories', 'roast', 'diagnosis', 'betterPrompt', 'footer'],
};

// A realistic mock verdict — used until an API key is wired, and as the fallback
// if a real call fails. Shaped exactly like a real verdict so the frontend can't
// tell the difference.
function mockVerdict(promptText) {
  const clean = (promptText || '').trim();
  return {
    prompt: clean || 'fix the error',
    score: 14,
    severity: 3,
    verdictLabel: 'BURNT · SEVERITY 3',
    primaryCategory: 'specificity',
    categories: { specificity: 14, tokens: 40, frontier: 55, tool: 62, context: 33, verify: 20 },
    roast: `"${clean || 'fix the error'}"? WHICH error, you donut? You've given me nothing. I've seen more detail on a parking ticket.`,
    diagnosis:
      "No error text, no file, no stack trace. The model has to guess what's broken, so it hallucinates a fix for a bug you never described. Zero specificity.",
    betterPrompt:
      'The checkout POST to /v1/orders returns 500.\nStack trace points to orders.ts:42 — `cart.total` is undefined\nfor guest carts. Here\'s the handler [paste]. Fix the null case\nand tell me why it only breaks for guests.',
    footer: 'logged → specificity · desk_buzzer',
  };
}

// Clamp/normalise whatever the scorer returns so the overlay never breaks on a
// bad field (out-of-range score, missing category, etc.).
function normaliseVerdict(v, promptText) {
  const clampScore = (n) => Math.max(0, Math.min(100, Math.round(Number(n) || 0)));
  const cats = v && v.categories ? v.categories : {};
  return {
    prompt: (promptText || v.prompt || '').trim(),
    score: clampScore(v.score),
    severity: [0, 1, 2, 3].includes(v.severity) ? v.severity : 2,
    verdictLabel: String(v.verdictLabel || 'RAW · SEVERITY 2'),
    primaryCategory: CATEGORY_KEYS.includes(v.primaryCategory) ? v.primaryCategory : 'specificity',
    categories: CATEGORY_KEYS.reduce((acc, k) => ((acc[k] = clampScore(cats[k])), acc), {}),
    roast: String(v.roast || ''),
    diagnosis: String(v.diagnosis || ''),
    betterPrompt: String(v.betterPrompt || ''),
    footer: String(v.footer || ''),
  };
}

module.exports = { CATEGORY_KEYS, CATEGORY_LABELS, VERDICT_SCHEMA, mockVerdict, normaliseVerdict };
