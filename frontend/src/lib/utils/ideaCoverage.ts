import { normalizeIdeaText } from "./normalizeIdeaText";

/**
 * Pure lexical coverage detector for the "Check my idea" pitch box (layer 1
 * of the clarify-intake design: a zero-LLM live coach). Flags whether the
 * typed text names WHO it's for, WHAT problem it solves, and HOW it's
 * delivered - the same three fields the layer-2 clarify call (POST
 * /api/suggest mode=clarify_idea) asks about when this heuristic can't tell.
 *
 * This is intentionally approximate: word lists and phrase frames, no NLP.
 * False positives/negatives just shift what the live checklist shows before
 * submit - the LLM-backed clarify call is the real gate.
 */
export interface IdeaCoverage {
  audience: boolean;
  problem: boolean;
  delivery: boolean;
  /** True when the ONLY audience-shaped signal found was a generic term
   *  (people/users/everyone/businesses) with nothing narrower behind it -
   *  `audience` is false in this case too, but the caller should show the
   *  "be more specific" hint instead of the plain "missing" one. */
  generic: boolean;
}

// ---- Audience -------------------------------------------------------

/** Curated role nouns not reliably caught by the suffix pattern below
 *  (plurals that don't end in -ers/-ists/-ians/-ors). ~40 entries. */
const ROLE_NOUNS = new Set([
  "parents", "students", "clients", "customers", "tenants", "landlords",
  "employees", "professionals", "consultants", "accountants", "teams",
  "founders", "startups", "agencies", "shops", "stores", "clinics",
  "practices", "firms", "hospitals", "schools", "nonprofits", "communities",
  "creators", "hosts", "guests", "patients", "couples", "families",
  "freelancers", "moms", "dads", "kids", "teens", "seniors", "veterans",
  "entrepreneurs", "specialists", "therapists", "physicians",
]);

/** Words that read as role-suffix matches but are common non-role plurals -
 *  excluded so "orders"/"errors" etc. don't false-positive as an audience. */
const SUFFIX_EXCLUDE = new Set([
  "others", "numbers", "orders", "matters", "letters", "offers", "answers",
  "papers", "folders", "servers", "quarters", "chapters", "dinners",
  "manners", "borders", "flowers", "powers", "towers", "waters",
  "computers", "browsers", "reminders", "features", "records", "reports",
  "doors", "colors", "errors", "floors", "mirrors", "sensors", "monitors",
  "factors",
]);

const ROLE_SUFFIX_RE = /(?:ers|ists|ians|ors)$/;

function hasRoleSuffix(token: string): boolean {
  return token.length >= 6 && !SUFFIX_EXCLUDE.has(token) && ROLE_SUFFIX_RE.test(token);
}

/** Generic-only gate: these alone don't count as naming an audience. */
const GENERIC_AUDIENCE_TERMS = ["people", "users", "everyone", "businesses"];

/** Preposition frames. Each captures the phrase that follows so we can
 *  check it isn't just stopwords (bare "for" appears in unrelated text
 *  constantly - "reasons for concern" shouldn't flag an audience). */
const AUDIENCE_FRAME_PATTERNS = [
  /\bbuilt for\s+([a-z][a-z' -]{1,40})/,
  /\bmade for\s+([a-z][a-z' -]{1,40})/,
  /\bdesigned for\s+([a-z][a-z' -]{1,40})/,
  /\baimed at\s+([a-z][a-z' -]{1,40})/,
  /\bhelps\s+([a-z][a-z' -]{1,40})/,
  /\bserves\s+([a-z][a-z' -]{1,40})/,
  /\btargets?\s+([a-z][a-z' -]{1,40})/,
  /\bfor\s+([a-z][a-z' -]{1,40})/,
];

const FRAME_STOPWORDS = new Set([
  "a", "an", "the", "your", "their", "our", "you", "us", "we", "my", "his",
  "her", "its", "this", "that", "these", "those", "and", "or", "to", "of",
  "with", "it", "them",
]);

/** Common abstract-goal nouns that follow "for" as often as an audience
 *  does ("a tool for productivity") - excluded so bare "for" doesn't
 *  false-positive on a purpose statement. */
const FRAME_NON_AUDIENCE_STARTERS = new Set([
  "productivity", "efficiency", "growth", "success", "speed", "accuracy",
  "clarity", "convenience", "simplicity", "automation", "collaboration",
  "communication", "organization", "management", "tracking", "scheduling",
  "invoicing", "everyone", "anyone", "free", "fun", "life", "work",
  "validation", "analytics", "testing", "monitoring", "optimization",
  "compliance", "marketing",
]);

/** Prepositions that end the head noun-phrase after a frame ("for UX
 *  validation of web interfaces" — the head NP is "ux validation"; the
 *  abstract-goal check must see "validation", not "interfaces"). */
const FRAME_HEAD_BOUNDARY = new Set(["of", "in", "on", "across", "from", "with", "via", "per"]);

function frameCapturesContent(pattern: RegExp, lower: string): boolean {
  const match = pattern.exec(lower);
  if (!match) return false;
  const raw = match[1].split(/\s+/).filter(Boolean);
  const boundary = raw.findIndex((word) => FRAME_HEAD_BOUNDARY.has(word));
  const head = (boundary === -1 ? raw : raw.slice(0, boundary)).filter(
    (word) => !FRAME_STOPWORDS.has(word),
  );
  if (head.length === 0) return false;
  const first = head[0];
  const last = head[head.length - 1];
  // A gerund right after the frame ("for tracking expenses") is almost
  // always describing an activity, not an audience.
  if (first.endsWith("ing")) return false;
  // Purpose statements name an abstract goal up front ("for productivity") or
  // as the head noun ("for UX validation") — both fail the audience frame.
  if (FRAME_NON_AUDIENCE_STARTERS.has(first) || FRAME_NON_AUDIENCE_STARTERS.has(last)) {
    return false;
  }
  return true;
}

function detectAudience(tokens: string[], lower: string): { met: boolean; generic: boolean } {
  const genericHit = GENERIC_AUDIENCE_TERMS.some((term) => tokens.includes(term));
  const roleNounHit = tokens.some((token) => ROLE_NOUNS.has(token));
  const suffixHit = tokens.some(
    (token) => !GENERIC_AUDIENCE_TERMS.includes(token) && hasRoleSuffix(token),
  );
  const specific = roleNounHit || suffixHit;

  if (specific) return { met: true, generic: false };
  // A generic noun with nothing specific backing it up: fails the gate.
  if (genericHit) return { met: false, generic: true };

  const frameHit = AUDIENCE_FRAME_PATTERNS.some((pattern) => frameCapturesContent(pattern, lower));
  return { met: frameHit, generic: false };
}

// ---- Problem ----------------------------------------------------------

/** Extends InputQualityMeter's QUALIFYING_WORDS with a broader pain
 *  vocabulary. Single tokens only - matched against the word list. */
const PAIN_LEXICON = [
  // InputQualityMeter's existing QUALIFYING_WORDS
  "struggling", "who", "need", "want", "trying", "can't", "overwhelmed", "stuck",
  // extended pain vocabulary
  "frustrated", "frustrating", "annoying", "tedious", "manually", "manual",
  "wastes", "wasting", "waste", "miss", "misses", "missed", "forget",
  "forgets", "forgot", "lose", "loses", "losing", "hard", "difficult",
  "painful", "slow", "messy", "chaos", "confusing", "scattered", "juggling",
  "chasing", "behind", "burned", "burnout", "expensive", "costly",
  "duplicate", "inconsistent", "errors", "mistakes", "delayed", "delays",
  "late", "overdue", "spreadsheets", "spreadsheet",
];

/** Causal frames - matched as substrings against the lowercased text. */
const CAUSAL_FRAMES = ["because", "so they don't", "so they can't", "instead of", "currently"];

function detectProblem(tokens: string[], lower: string): boolean {
  const lexiconHit = PAIN_LEXICON.some((word) => tokens.includes(word));
  const causalHit = CAUSAL_FRAMES.some((frame) => lower.includes(frame));
  return lexiconHit || causalHit;
}

// ---- Delivery -----------------------------------------------------------

/** Form nouns, single-token. Deliberately EXCLUDES "tool"/"platform"/
 *  "software" - those alone must fail so the checklist pushes for a real
 *  form ("Say what form it takes"). */
const DELIVERY_FORM_WORDS = [
  "app", "extension", "plugin", "saas", "api", "bot", "chatbot",
  "dashboard", "widget", "addon", "integration", "spreadsheet", "template",
  "script", "automation", "workflow", "cli", "library", "sdk", "service",
  "webapp", "newsletter", "database",
];

/** Form nouns that only make sense as multi-word phrases - matched as
 *  substrings against the lowercased text. */
const DELIVERY_FORM_PHRASES = [
  "add-on", "chrome extension", "browser extension", "mobile app", "web app",
  "slack bot", "google sheet",
];

/** Delivery verbs - matched as substrings against the lowercased text. */
const DELIVERY_VERB_FRAMES = ["runs on", "plugs into", "integrates with", "connects to", "syncs with"];

function detectDelivery(tokens: string[], lower: string): boolean {
  const formWordHit = DELIVERY_FORM_WORDS.some((word) => tokens.includes(word));
  const formPhraseHit = DELIVERY_FORM_PHRASES.some((phrase) => lower.includes(phrase));
  const verbHit = DELIVERY_VERB_FRAMES.some((frame) => lower.includes(frame));
  return formWordHit || formPhraseHit || verbHit;
}

// ---- Entry point --------------------------------------------------------

function normalizeForMatching(text: string): string {
  return normalizeIdeaText(text).toLowerCase();
}

export function detectIdeaCoverage(text: string): IdeaCoverage {
  const lower = normalizeForMatching(text);
  const tokens = lower.match(/[a-z']+/g) ?? [];

  const audience = detectAudience(tokens, lower);
  const problem = detectProblem(tokens, lower);
  const delivery = detectDelivery(tokens, lower);

  return {
    audience: audience.met,
    problem,
    delivery,
    generic: audience.generic,
  };
}

/** Maps a coverage result to the checklist rows InputQualityMeter renders.
 *  Row labels share the vocabulary used across all three clarify-intake
 *  layers ("Who it's for / Problem it solves / How it works"), swapped for
 *  a corrective hint in the two heuristics that call one out by name. */
export function buildCoverageChecklist(coverage: IdeaCoverage): { label: string; met: boolean }[] {
  return [
    { label: coverage.generic ? "Name a narrower group" : "Who it's for", met: coverage.audience },
    { label: "Problem it solves", met: coverage.problem },
    { label: coverage.delivery ? "How it works" : "Say what form it takes", met: coverage.delivery },
  ];
}
