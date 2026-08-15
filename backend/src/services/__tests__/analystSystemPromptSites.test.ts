import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const HERE = dirname(fileURLToPath(import.meta.url));
const BACKEND = resolve(HERE, '..', '..', '..');

/**
 * THE ROUND'S REAL DELIVERABLE — every generator that writes model-authored prose on an
 * idea-check run, and the mechanical proof that each one receives the framing.
 *
 * Nine rounds fixed nineteen surfaces one at a time. Two of them were LLM prompts, and both
 * were fixed by ADDING A PARAMETER: `buildG3SystemPrompt(..., ideaCheck = 'none')` and then
 * `buildCompletedReportSystemPrompt(..., ideaCheck = 'none')`. That shape cannot enumerate
 * itself. A third generator (`generateSuggestions`) and a fourth (`analystFollowupService`)
 * were written without the parameter, wrote prose on refused runs, PERSISTED it — and nothing
 * anywhere went red. The critic that found them had to read thirteen call sites by hand.
 *
 * So the property is no longer "the parameter is passed". It is:
 *
 *   EVERY `chatComplete` / `chatCompleteStream` call whose messages MAY include a `system`
 *   role must take that content from `composeAnalystSystemPrompt`, the only producer of the
 *   `AnalystSystemPrompt` brand, which inserts the idea-check clause from the context itself.
 *
 * ── WHAT THIS SCAN IS, AND EXACTLY WHAT IT CHECKS (round 11) ────────────────────────────
 *
 * The `AnalystSystemPrompt` brand is a `tsc` CONVENTION, not a runtime type:
 * `ChatCompletionMessageParam.content` is `string`, so a plain string reaches the provider
 * unchallenged and only a cast is needed to satisfy the compiler. **This scan is therefore
 * the only enforcement there is**, and round 10's claim that no generator "can" miss the
 * framing was true only of generators the scan could see. A round-11 critic broke it five
 * ways, all compiling cleanly: a `.push` of a system message two lines below the literal the
 * scan protected (the idiom already in `chat.ts`), a hoisted message object, a same-file
 * function whose declared return type was the brand and whose body was a cast, a `role:`
 * resolved through a const, and a spread of a system-message array. Four more were found by
 * this round. All nine were GREEN.
 *
 * The rewrite's rule is one sentence: **anything the walker cannot fully resolve to object
 * literals scores UNFRAMED.** Absence of a visible system message used to be the passing
 * case; it is now the failing case, because "I could not see a system message" and "there is
 * no system message" are the same observation from a walker's point of view and only one of
 * them is safe.
 *
 * ── ROUND 12: THE RULE NOW GOVERNS DISCOVERY TOO ─────────────────────────────────────────
 *
 * Round 11 applied that sentence to what was INSIDE a site and not to whether something WAS
 * one. Finding a site required an identifier callee spelled exactly `chatComplete` /
 * `chatCompleteStream` AND an object literal in argument 0; break either conjunct and the call
 * yielded NO SITE — from here, the same reading as a file with no LLM call in it. Ten shapes
 * walked past, all compiling: see the D-n controls. The escape was live precisely INSIDE the
 * two files already in `ANALYST_FILES`, which is where surfaces 4, 19, 20 and 21 all lived,
 * and every generator this program has ever missed was added to `chat.ts`.
 *
 *   A call that reaches an entry point ALWAYS yields a site. When the callee or the options
 *   cannot be read, that site is UNFRAMED — never absent.
 *
 * The same round closed the exact sibling: `PRESERVING` returned `true` on a callee's NAME
 * without looking at its argument, so this file's own headline forgery went GREEN when wrapped
 * in `appendToAnalystSystemPrompt(…, '')`. A preserving helper is judged on what it is GIVEN.
 *
 * Concretely, a site is FRAMED only when all of this holds:
 *   0. the call is to an entry point under any spelling — the bare name, an import alias, a
 *      namespace or object method, an element access, or a local alias of the binding — and
 *      its options object resolves through consts and ternaries to object literals. `.call` /
 *      `.apply` / `.bind`, an options builder's return value and a spread argument do not
 *      resolve, and unresolved is unframed;
 *   1. the `messages` value resolves, transitively, to a fixed list of object literals —
 *      through consts, reassignments, `.push`/`.unshift`, spreads, ternaries and the one
 *      `history.map(arrow)` shape the real route uses. Anything else (a call, a parameter,
 *      `Object.assign`, a `.splice`, the array escaping into another function) is UNRESOLVED,
 *      and unresolved is unframed;
 *   2. every entry's `role` resolves to a string literal — through same-file consts and
 *      `as const`. A role that does not resolve is treated as `system`;
 *   3. every system entry's `content` derives from `composeAnalystSystemPrompt`, following
 *      consts, ternaries, and INTO THE BODY of a same-file function (every `return` must
 *      derive; the declared return type is not consulted, because a declared type is exactly
 *      what a cast forges). `x as AnalystSystemPrompt`, template concatenation and calls to
 *      anything defined outside the file are unframed.
 *
 * What it still cannot see, stated so no future reader believes more than it does:
 *   - a system prompt built in another module and imported. Such a module is itself an
 *     analyst file: the inventory below forces it into `ANALYST_FILES`, where this scan runs
 *     on it — but the FLOW between the two files is not traced, so a helper that returns a
 *     bare string from a file with no LLM call of its own is invisible here. (`tsc` catches
 *     the common case: the value has to be an `AnalystSystemPrompt` to be typed as one.)
 *   - an array reaching the call through a shape with no name at all — an IIFE result, a
 *     `Map.get`, a property on an object built elsewhere. All of those are UNRESOLVED, which
 *     is the failing verdict, so they are not escapes; they are false positives waiting to
 *     happen, and the fix when one appears is to give the array a name.
 *
 * (An earlier draft of this comment listed alias mutation — `const alias = messages;
 * alias.push(...)` — as a known limit. It was: measured GREEN. It is closed instead of
 * documented, control M-10, because writing a limit down is not a substitute for removing
 * it when removing it is twenty lines.)
 *
 * ─────────────────────────────────────────────────────────────────────────────────────
 * WHAT THIS FILE IS, NOW THAT THE PROGRAM AROUND IT IS CLOSED (2026-08-15).
 *
 * THIS SCAN IS A TRIPWIRE FOR ACCIDENTS. IT IS NOT A PROOF AGAINST DETERMINED CODE.
 * Read that as a statement about its reach, not its quality: it reliably catches the way a
 * generator gets added by someone who does not know the framing rule exists, which is how
 * every generator this program actually missed was added. It does not, and cannot as built,
 * stop code written to get past it.
 *
 * Two whole CLASSES are invisible, and neither is closable by adding spellings:
 *
 *   (A) A CALL REACHING AN ENTRY POINT UNDER A DIFFERENT NAME. Site discovery matches the
 *       callee against `LLM_CALLS` (and `classifyCallee` against `PRODUCER` /
 *       `BRAND_PRESERVING`) by the name written at the call. Any indirection that preserves
 *       the function while changing the name it is called by produces ZERO SITES — reported
 *       identically to a file with no LLM call in it. Four such spellings were found in one
 *       afternoon after round 12, recorded here so nobody rediscovers them as news:
 *         1. an object property:   `const api = { ask: chatComplete }; api.ask({…})`
 *         2. a class field:        `class C { send = chatComplete } new C().send({…})`
 *         3. a destructured rename: `const { chatComplete: talk } = mod; talk({…})`
 *       There is no reason to think those three are the only three.
 *
 *   (B) A SAME-FILE SHADOW OF A TRUSTED NAME. `classifyCallee` returns FRAMED when the callee
 *       spells `PRODUCER` or a `BRAND_PRESERVING` key. A local declaration of that same name
 *       in an analyst file is trusted on its spelling alone:
 *         4. `function composeAnalystSystemPrompt(_ctx, parts) { return parts.body }`
 *            — discards its context argument, emits an unframed string, and still scores
 *            FRAMED, because trust here is attached to a NAME and names are shadowable.
 *
 * DO NOT CLOSE THESE BY ENUMERATING SPELLINGS. That is trap 5 in
 * `docs/SEED_IDENTITY_REMEDIATION.md`, and `classifyCallee` growing one spelling at a time is
 * the reason this keeps recurring: every thread in this program that actually closed did so by
 * removing a mechanism or fixing the property, never by lengthening a list. A real fix for (A)
 * is identity-based rather than name-based (resolve the imported symbol, or make the framing
 * unskippable at the call boundary so there is no unframed shape to reach); a real fix for (B)
 * is to stop trusting a bare name in a file that is allowed to declare it.
 *
 * Until then this file is frozen deliberately, with its reach written down rather than
 * overclaimed. A green run here means "no ACCIDENTAL unframed generator in the two listed
 * files". It has never meant more than that, and this paragraph exists so no future round
 * reads it as more.
 * ─────────────────────────────────────────────────────────────────────────────────────
 */

/** Every file that may talk to the analyst model. Named, because the point is that the LIST
 *  OF FILES is short and auditable while the list of GENERATORS inside them is not. A file
 *  added here with an unframed prompt fails; a file NOT added is covered by the inventory,
 *  which finds model access by IMPORT rather than by call-name spelling. */
const ANALYST_FILES = [
  'src/routes/chat.ts',
  'src/services/analystFollowupService.ts',
];

const LLM_CALLS = new Set(['chatComplete', 'chatCompleteStream']);
const PRODUCER = 'composeAnalystSystemPrompt';
/**
 * Helpers that PRESERVE the brand of an argument rather than producing it, and the index of
 * the argument whose brand is carried through.
 *
 * Round 11 held these in a name whitelist that returned `true` on the callee's SPELLING without
 * ever looking at what it was handed, so `appendToAnalystSystemPrompt(raw as AnalystSystemPrompt,
 * '')` — that round's own headline forgery with a whitelisted wrapper around it — scored FRAMED.
 * A preserving helper is judged on what it is GIVEN. Appending still cannot remove the clause;
 * that is exactly why the verdict is the ARGUMENT's, unchanged, rather than an unconditional yes.
 */
const BRAND_PRESERVING: Record<string, number> = { appendToAnalystSystemPrompt: 0 };
/** Ways to invoke a function without naming it in callee position. Options move to another
 *  argument (`.call`) or vanish into an array (`.apply`), so these are never readable here. */
const INVOCATION_ADAPTERS = new Set(['call', 'apply', 'bind']);
/** Array methods that can introduce an element the walker has not seen. (`concat` is absent
 *  on purpose: it returns a new array and leaves the receiver alone — a `.concat` result used
 *  AS the messages value is unresolvable for a different reason, and is caught there.) */
const ARRAY_MUTATORS = new Set(['push', 'unshift', 'splice', 'fill', 'copyWithin']);

interface Site {
  file: string;
  line: number;
  framed: boolean;
  detail: string;
}

/** Everything the walker learned about one file, in one pass. */
/**
 * ── THE BINDING MODEL ───────────────────────────────────────────────────────────────────
 *
 * Round 10 resolved identifiers through one flat `Map<name, Expression[]>` for the whole
 * file. `chat.ts` declares `messages` TWICE — the analyst tool loop at 3520 and an unrelated
 * publication list at 4236 — so a flat map answers "what is `messages`?" with both, and the
 * first version of this rewrite duly failed the real route with a complaint about a `row`
 * from the other function. Names are therefore resolved through SCOPES: a binding belongs to
 * the nearest enclosing function (or the file), and a use site sees the innermost binding
 * visible from where it stands. A parameter shadows an outer name and carries no assignment,
 * which resolves to "unresolved" — the safe direction.
 */
type Scope = ts.Node;

interface Binding {
  name: string;
  /** Every expression ever assigned: the declaration's initializer plus later `=`. */
  assignments: ts.Expression[];
  /** Everything appended by `.push` / `.unshift` / `x[i] = …`, wherever in the file. */
  appended: ts.Expression[];
  /** Non-null when the walker had to give up: an opaque mutation, or an escape into a call. */
  escaped: string | null;
  /** Set when the binding is a function: its parameter names, in order. */
  params: string[] | null;
  /** Set when the binding is a function: its own `return` expressions. */
  returns: ts.Expression[] | null;
  /** A function whose returns the walker could not read (no body, or a bare `return;`). */
  opaqueFn: boolean;
  /** The function node itself, when this binding is a function — its scope holds its params. */
  fnNode: Scope | null;
  /** `const alias = messages` — what this name is a second handle on. */
  aliasOf: ts.Identifier | null;
}

interface FileFacts {
  sf: ts.SourceFile;
  scopes: Map<Scope, Map<string, Binding>>;
}

const isScope = (node: ts.Node): boolean =>
  ts.isSourceFile(node)
  || ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node)
  || ts.isArrowFunction(node) || ts.isMethodDeclaration(node)
  || ts.isConstructorDeclaration(node) || ts.isGetAccessorDeclaration(node)
  || ts.isSetAccessorDeclaration(node);

/** The scope a declaration at `node` belongs to (its nearest enclosing function or the file). */
function enclosingScope(node: ts.Node): Scope {
  let cur: ts.Node | undefined = node.parent;
  while (cur && !isScope(cur)) cur = cur.parent;
  return cur ?? node.getSourceFile();
}

/** Innermost-first list of scopes visible from `node`. */
function scopeChain(node: ts.Node): Scope[] {
  const chain: Scope[] = [];
  let cur: ts.Node | undefined = node;
  while (cur) {
    if (isScope(cur)) chain.push(cur);
    cur = cur.parent;
  }
  return chain;
}

function emptyBinding(name: string): Binding {
  return {
    name, assignments: [], appended: [], escaped: null,
    params: null, returns: null, opaqueFn: false, fnNode: null, aliasOf: null,
  };
}

function declare(facts: FileFacts, scope: Scope, name: string): Binding {
  let table = facts.scopes.get(scope);
  if (!table) {
    table = new Map();
    facts.scopes.set(scope, table);
  }
  let binding = table.get(name);
  if (!binding) {
    binding = emptyBinding(name);
    table.set(name, binding);
  }
  return binding;
}

/** The binding `name` refers to when used at `from`, or null when nothing in this file declares it. */
function lookup(facts: FileFacts, name: string, from: ts.Node): Binding | null {
  for (const scope of scopeChain(from)) {
    const found = facts.scopes.get(scope)?.get(name);
    if (found) return found;
  }
  return null;
}

function functionReturns(body: ts.Node): { returns: ts.Expression[]; opaque: boolean } {
  const returns: ts.Expression[] = [];
  let opaque = false;
  const walk = (node: ts.Node) => {
    // Do not descend into a nested function: its returns are not this function's returns.
    if (
      ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node)
      || ts.isArrowFunction(node) || ts.isMethodDeclaration(node)
    ) return;
    if (ts.isReturnStatement(node)) {
      if (node.expression) returns.push(node.expression);
      else opaque = true; // `return;` from a prompt builder — cannot derive anything.
    }
    ts.forEachChild(node, walk);
  };
  ts.forEachChild(body, walk);
  return { returns, opaque };
}

function attachFunction(binding: Binding, fn: ts.SignatureDeclaration & { body?: ts.Node }): void {
  binding.params = fn.parameters.map((p) => (ts.isIdentifier(p.name) ? p.name.text : ''));
  binding.fnNode = fn;
  const body = fn.body;
  if (!body) {
    binding.opaqueFn = true;
    binding.returns = [];
    return;
  }
  if (!ts.isBlock(body)) {
    binding.returns = [body as ts.Expression]; // concise arrow body
    return;
  }
  const { returns, opaque } = functionReturns(body);
  binding.returns = returns;
  if (opaque || returns.length === 0) binding.opaqueFn = true;
}

function collectFacts(sf: ts.SourceFile): FileFacts {
  const facts: FileFacts = { sf, scopes: new Map() };

  // ── Pass 1: declarations. Every name gets a home scope before anything is resolved.
  const declarePass = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const binding = declare(facts, enclosingScope(node), node.name.text);
      if (node.initializer) {
        binding.assignments.push(node.initializer);
        // `const alias = messages` — a second handle on the same array. Recorded so a
        // `.push` through the alias reaches the original; see the propagation pass.
        const bare = unwrap(node.initializer);
        if (ts.isIdentifier(bare)) binding.aliasOf = bare;
        if (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer)) {
          attachFunction(binding, node.initializer);
        }
      }
    }
    if ((ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)) && node.name && ts.isIdentifier(node.name)) {
      attachFunction(declare(facts, enclosingScope(node), node.name.text), node);
    }
    // Parameters shadow outer names and hold no visible value: declared, never assigned.
    if (isScope(node) && !ts.isSourceFile(node)) {
      for (const param of (node as ts.SignatureDeclaration).parameters ?? []) {
        if (ts.isIdentifier(param.name)) declare(facts, node, param.name.text);
      }
    }
    ts.forEachChild(node, declarePass);
  };
  declarePass(sf);

  // ── Pass 2: writes, mutations and escapes, each resolved to the binding it actually hits.
  const argPassings: { arg: ts.Identifier; callee: ts.Expression }[] = [];
  const writePass = (node: ts.Node) => {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
      if (ts.isIdentifier(node.left)) {
        lookup(facts, node.left.text, node)?.assignments.push(node.right);
      }
      // `messages[0] = …` — an opaque write into an otherwise resolved list.
      if (ts.isElementAccessExpression(node.left) && ts.isIdentifier(node.left.expression)) {
        lookup(facts, node.left.expression.text, node)?.appended.push(node.right);
      }
    }
    if (ts.isCallExpression(node)) {
      const callee = node.expression;
      if (
        ts.isPropertyAccessExpression(callee)
        && ts.isIdentifier(callee.expression)
        && ARRAY_MUTATORS.has(callee.name.text)
      ) {
        const target = lookup(facts, callee.expression.text, node);
        if (target) {
          if (callee.name.text === 'push' || callee.name.text === 'unshift') {
            for (const arg of node.arguments) target.appended.push(arg);
          } else {
            target.escaped = `mutated by .${callee.name.text}()`;
          }
        }
      }
      for (const arg of node.arguments) {
        if (!ts.isIdentifier(arg)) continue;
        if (ts.isIdentifier(callee) && LLM_CALLS.has(callee.text)) continue;
        argPassings.push({ arg, callee });
      }
    }
    ts.forEachChild(node, writePass);
  };
  writePass(sf);

  /**
   * ── Pass 2b: aliases. `const alias = messages; alias.push({ role: 'system', … })` mutates
   * the SAME array, and resolving `messages` would never look at `alias`. Everything appended
   * to (or escaped from) an alias is folded back into the binding it aliases, transitively.
   */
  for (let pass = 0; pass < 4; pass += 1) {
    for (const table of facts.scopes.values()) {
      for (const binding of table.values()) {
        if (!binding.aliasOf) continue;
        const target = lookup(facts, binding.aliasOf.text, binding.aliasOf);
        if (!target || target === binding) continue;
        for (const extra of binding.appended) {
          if (!target.appended.includes(extra)) target.appended.push(extra);
        }
        if (binding.escaped && !target.escaped) {
          target.escaped = `aliased by \`${binding.name}\`, which ${binding.escaped}`;
        }
      }
    }
  }

  /**
   * ── Pass 3: arrays handed to other functions.
   *
   * Passing the messages array to another function is a laundering path only if that function
   * can ADD to it. When the callee is declared in this file the walker can answer that: find
   * the parameter the argument lands on, then ask whether THAT binding is ever appended to or
   * passed on. A callee this file does not declare (imported, or a method call) cannot be
   * read at all, so it escapes. `chat.ts` relies on this: the tool-loop array is handed to
   * `generateSuggestions(…)`, whose `history` parameter it only reads.
   */
  for (const { arg, callee } of argPassings) {
    const binding = lookup(facts, arg.text, arg);
    if (!binding || binding.escaped) continue;
    const calleeBinding = ts.isIdentifier(callee) ? lookup(facts, callee.text, callee) : null;
    if (!calleeBinding || !calleeBinding.params) {
      binding.escaped = `passed to ${callee.getText().slice(0, 40)}(), which this file does not declare`;
      continue;
    }
    const index = (callee.parent as ts.CallExpression).arguments.indexOf(arg);
    const paramName = calleeBinding.params[index];
    if (!paramName || !calleeBinding.fnNode) {
      binding.escaped = `passed to ${callee.getText().slice(0, 40)}() in a position with no readable parameter`;
      continue;
    }
    const paramBinding = facts.scopes.get(calleeBinding.fnNode)?.get(paramName);
    if (!paramBinding || paramBinding.appended.length > 0 || paramBinding.escaped) {
      binding.escaped = `passed to ${callee.getText().slice(0, 40)}(), whose \`${paramName}\` is mutated or passed on`;
    }
  }
  return facts;
}

/** Resolution result: a fixed list of message object literals, or the reason there is none. */
type Entries = { ok: true; entries: ts.ObjectLiteralExpression[] } | { ok: false; why: string };

const unresolved = (why: string): Entries => ({ ok: false, why });

function unwrap(node: ts.Expression): ts.Expression {
  let cur = node;
  for (;;) {
    if (ts.isParenthesizedExpression(cur) || ts.isNonNullExpression(cur)) cur = cur.expression;
    else if (ts.isAsExpression(cur) || ts.isSatisfiesExpression(cur)) cur = cur.expression;
    else return cur;
  }
}

/** One message ENTRY (an element of the messages array), resolved to object literals. */
function resolveEntry(expr: ts.Expression, facts: FileFacts, seen: Set<Binding>): Entries {
  const node = unwrap(expr);
  if (ts.isObjectLiteralExpression(node)) return { ok: true, entries: [node] };
  if (ts.isConditionalExpression(node)) {
    const a = resolveEntry(node.whenTrue, facts, seen);
    if (!a.ok) return a;
    const b = resolveEntry(node.whenFalse, facts, seen);
    if (!b.ok) return b;
    return { ok: true, entries: [...a.entries, ...b.entries] };
  }
  if (ts.isIdentifier(node)) {
    const binding = lookup(facts, node.text, node);
    if (!binding) return unresolved(`\`${node.text}\` is not declared in this file (import? parameter?)`);
    if (seen.has(binding)) return unresolved(`cyclic reference to \`${node.text}\``);
    if (binding.escaped) return unresolved(`\`${node.text}\` ${binding.escaped}`);
    if (binding.assignments.length === 0) {
      return unresolved(`\`${node.text}\` has no visible assignment (parameter?)`);
    }
    const next = new Set(seen).add(binding);
    const out: ts.ObjectLiteralExpression[] = [];
    for (const source of binding.assignments) {
      const r = resolveEntry(source, facts, next);
      if (!r.ok) return r;
      out.push(...r.entries);
    }
    return { ok: true, entries: out };
  }
  return unresolved(`message entry is \`${node.getText().slice(0, 48)}\``);
}

/**
 * The messages ARRAY, resolved to a fixed list of entries. Anything that does not resolve
 * returns `ok: false` and the site is scored unframed — the round-11 rule.
 */
function resolveMessages(expr: ts.Expression, facts: FileFacts, seen: Set<Binding>): Entries {
  const node = unwrap(expr);

  if (ts.isArrayLiteralExpression(node)) {
    const out: ts.ObjectLiteralExpression[] = [];
    for (const el of node.elements) {
      if (ts.isOmittedExpression(el)) continue;
      const r = ts.isSpreadElement(el)
        ? resolveMessages(el.expression, facts, seen)
        : resolveEntry(el, facts, seen);
      if (!r.ok) return r;
      out.push(...r.entries);
    }
    return { ok: true, entries: out };
  }

  if (ts.isConditionalExpression(node)) {
    const a = resolveMessages(node.whenTrue, facts, seen);
    if (!a.ok) return a;
    const b = resolveMessages(node.whenFalse, facts, seen);
    if (!b.ok) return b;
    return { ok: true, entries: [...a.entries, ...b.entries] };
  }

  // `history.map((h) => …)` — the one call shape the real route uses to splice prior turns
  // into the array. RESOLVED, not exempted: the arrow's returned literals ARE the entries, so
  // a `.map` that produced a system message is caught like any other.
  if (
    ts.isCallExpression(node)
    && ts.isPropertyAccessExpression(node.expression)
    && node.expression.name.text === 'map'
    && node.arguments.length === 1
  ) {
    const fn = unwrap(node.arguments[0] as ts.Expression);
    if (!ts.isArrowFunction(fn)) return unresolved('`.map` argument is not an inline arrow');
    if (!ts.isBlock(fn.body)) return resolveEntry(fn.body, facts, seen);
    const { returns, opaque } = functionReturns(fn.body);
    if (opaque || returns.length === 0) return unresolved('`.map` callback has no plain return');
    const out: ts.ObjectLiteralExpression[] = [];
    for (const r0 of returns) {
      const r = resolveEntry(r0, facts, seen);
      if (!r.ok) return r;
      out.push(...r.entries);
    }
    return { ok: true, entries: out };
  }

  if (ts.isIdentifier(node)) {
    const binding = lookup(facts, node.text, node);
    if (!binding) return unresolved(`\`${node.text}\` is not declared in this file (import? parameter?)`);
    if (seen.has(binding)) return unresolved(`cyclic reference to \`${node.text}\``);
    if (binding.escaped) return unresolved(`\`${node.text}\` ${binding.escaped}`);
    if (binding.assignments.length === 0) {
      return unresolved(`\`${node.text}\` has no visible assignment (parameter?)`);
    }
    const next = new Set(seen).add(binding);
    const out: ts.ObjectLiteralExpression[] = [];
    for (const source of binding.assignments) {
      const r = resolveMessages(source, facts, next);
      if (!r.ok) return r;
      out.push(...r.entries);
    }
    // …AND everything appended to it anywhere in the file. This is the shape that sat two
    // lines below the literal the round-10 scan protected.
    for (const extra of binding.appended) {
      const r = ts.isSpreadElement(extra)
        ? resolveMessages(extra.expression, facts, next)
        : resolveEntry(extra as ts.Expression, facts, next);
      if (!r.ok) return r;
      out.push(...r.entries);
    }
    return { ok: true, entries: out };
  }

  return unresolved(`messages is \`${node.getText().slice(0, 48)}\``);
}

/** A string-valued expression, resolved through same-file consts and `as const`. */
function resolveStringLiteral(
  expr: ts.Expression,
  facts: FileFacts,
  seen = new Set<Binding>(),
): string | null {
  const node = unwrap(expr);
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isIdentifier(node)) {
    const binding = lookup(facts, node.text, node);
    if (!binding || seen.has(binding) || binding.assignments.length !== 1) return null;
    return resolveStringLiteral(binding.assignments[0], facts, new Set(seen).add(binding));
  }
  return null;
}

/**
 * Does this expression come, transitively, from the one producer?
 *
 * The declared return type is deliberately NOT consulted. Round 10's version accepted any
 * call whose callee declared `: AnalystSystemPrompt`, on the stated grounds that "only
 * `composeAnalystSystemPrompt` can produce" such a value — which the same file disproved two
 * controls later by planting the cast that forges it. The BODY is read instead: every
 * `return` of a same-file callee must itself derive from the factory.
 */

/**
 * Tri-state, and the third state is load-bearing. The shipped route writes
 * `systemPrompt = appendToAnalystSystemPrompt(systemPrompt, …)` twice, which is a FIXPOINT: it
 * neither produces the brand nor destroys it. Now that a preserving helper is judged on its
 * argument, that assignment resolves back into the binding being resolved. Calling such a cycle
 * `false` fails the real file; calling it `true` would let `const a = b; const b = a;` mint a
 * brand out of nothing. It is NEUTRAL instead — it contributes no evidence — and a value whose
 * every source is neutral has no evidence at all, which is `false`.
 */
type Derivation = true | false | 'cycle';

/** All sources must derive; a neutral source is skipped; nothing concrete left is not derived. */
function allDerive(results: Derivation[]): Derivation {
  if (results.length === 0) return false;
  if (results.some((r) => r === false)) return false;
  return results.some((r) => r === true) ? true : 'cycle';
}

function deriveFromFactory(node: ts.Expression, facts: FileFacts, seen = new Set<Binding>()): Derivation {
  if (ts.isParenthesizedExpression(node) || ts.isNonNullExpression(node)) {
    return deriveFromFactory(node.expression, facts, seen);
  }
  if (ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) {
    // Deliberately NOT unwrapped: `x as AnalystSystemPrompt` outside the factory is exactly
    // the escape this scan exists to catch.
    return false;
  }
  if (ts.isConditionalExpression(node)) {
    return allDerive([
      deriveFromFactory(node.whenTrue, facts, seen),
      deriveFromFactory(node.whenFalse, facts, seen),
    ]);
  }
  if (ts.isIdentifier(node)) {
    const binding = lookup(facts, node.text, node);
    if (!binding || binding.assignments.length === 0) return false;
    if (seen.has(binding)) return 'cycle';
    const next = new Set(seen).add(binding);
    return allDerive(binding.assignments.map((source) => deriveFromFactory(source, facts, next)));
  }
  if (ts.isCallExpression(node)) {
    const callee = node.expression;
    if (!ts.isIdentifier(callee)) return false;
    if (callee.text === PRODUCER) return true;
    const carries = BRAND_PRESERVING[callee.text];
    if (carries !== undefined) {
      // Judged on WHAT IT IS GIVEN. A missing or spread argument is unreadable: fail closed.
      const arg = callee.text && node.arguments[carries];
      if (!arg || ts.isSpreadElement(arg)) return false;
      return deriveFromFactory(arg, facts, seen);
    }
    const binding = lookup(facts, callee.text, callee);
    // A function defined elsewhere (imported, or held in a parameter) cannot be read: fail closed.
    if (!binding || binding.returns === null || binding.opaqueFn) return false;
    if (seen.has(binding)) return 'cycle';
    if (binding.returns.length === 0) return false;
    const next = new Set(seen).add(binding);
    return allDerive(binding.returns.map((r) => deriveFromFactory(r, facts, next)));
  }
  return false;
}

function producedByFactory(node: ts.Expression, facts: FileFacts): boolean {
  return deriveFromFactory(node, facts) === true;
}

/**
 * ── WHAT COUNTS AS A SITE ────────────────────────────────────────────────────────────────
 *
 * Round 11's rule — "anything the walker cannot fully resolve scores UNFRAMED" — governed what
 * was INSIDE a site. It did not govern whether something WAS one. Discovery demanded an
 * identifier callee spelled exactly `chatComplete`/`chatCompleteStream` AND an object literal
 * sitting in argument 0; break either conjunct and the call produced NO SITE, which from here is
 * indistinguishable from "this file contains no LLM call". That is the ledger's trap 19 — "could
 * not determine" and "determined to be fine" must be different verdicts — one level below where
 * round 11 applied it. Ten shapes walked straight past it, all compiling: a hoisted options
 * object, a same-file options builder, `import { chatComplete as ask }`, a namespace callee, a
 * local alias of the binding, `.call`, a comma-expression callee, a cast on the options object,
 * a conditional options object, and an element-access callee. Hoisting an options object is a
 * routine refactor, not an adversarial act, and the escape is live precisely INSIDE the two
 * files already in `ANALYST_FILES` — where surfaces 4, 19, 20 and 21 all lived.
 *
 * A call that reaches an entry point now ALWAYS yields a site. When the callee or the options
 * cannot be read, that site is UNFRAMED — never absent.
 */
type CalleeVerdict =
  /** The entry point is called directly: its options are argument 0. */
  | { kind: 'direct'; name: string }
  /** It is reached by a shape that moves or hides the options. Never readable from here. */
  | { kind: 'opaque'; why: string }
  | null;

/** Local names that reach an entry point: the bare spellings plus every import alias.
 *  The inventory already resolves aliases through the import graph; these now agree. */
function llmLocalNames(sf: ts.SourceFile): Set<string> {
  const names = new Set(LLM_CALLS);
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !stmt.importClause) continue;
    const bound = stmt.importClause.namedBindings;
    if (!bound || !ts.isNamedImports(bound)) continue;
    for (const el of bound.elements) {
      if (LLM_CALLS.has((el.propertyName ?? el.name).text)) names.add(el.name.text);
    }
  }
  return names;
}

/** Parens, casts and `(0, f)` stripped off a callee position. The comma form is handled but
 *  has no control: `(0, chatComplete)(…)` is TS2695 under this tsconfig, so it cannot be
 *  planted as compiling code. `(chatComplete as typeof chatComplete)(…)` is D-7 in its place. */
function unwrapCallee(expr: ts.Expression): ts.Expression {
  let cur = unwrap(expr);
  while (ts.isBinaryExpression(cur) && cur.operatorToken.kind === ts.SyntaxKind.CommaToken) {
    cur = unwrap(cur.right);
  }
  return cur;
}

function classifyCallee(
  expr: ts.Expression,
  facts: FileFacts,
  names: Set<string>,
  seen = new Set<Binding>(),
): CalleeVerdict {
  const node = unwrapCallee(expr);
  // `(flag ? chatComplete : somethingElse)(…)`. Either branch reaching an entry point makes
  // this a site — found while compiling D-7 and, until then, an escape in this rewrite too.
  if (ts.isConditionalExpression(node)) {
    return classifyCallee(node.whenTrue, facts, names, seen)
      ?? classifyCallee(node.whenFalse, facts, names, seen);
  }
  if (ts.isIdentifier(node)) {
    if (names.has(node.text)) return { kind: 'direct', name: node.text };
    // `const ask = chatComplete;` — a local second handle on the binding.
    const binding = lookup(facts, node.text, node);
    if (!binding || seen.has(binding) || binding.assignments.length === 0) return null;
    const next = new Set(seen).add(binding);
    for (const source of binding.assignments) {
      const found = classifyCallee(source, facts, names, next);
      if (found) return found;
    }
    return null;
  }
  if (ts.isPropertyAccessExpression(node)) {
    // `llm.chatComplete(…)` — a namespace or object callee. The METHOD is the entry point.
    if (names.has(node.name.text)) return { kind: 'direct', name: node.name.text };
    if (INVOCATION_ADAPTERS.has(node.name.text) && classifyCallee(node.expression, facts, names, seen)) {
      return { kind: 'opaque', why: `reached through .${node.name.text}()` };
    }
    return null;
  }
  if (ts.isElementAccessExpression(node) && node.argumentExpression) {
    const key = resolveStringLiteral(node.argumentExpression, facts);
    if (key && names.has(key)) return { kind: 'direct', name: key };
  }
  return null;
}

/** The options object handed to an entry point, resolved to a fixed list of object literals. */
type Options =
  | { ok: true; objects: ts.ObjectLiteralExpression[] }
  | { ok: false; why: string };

function resolveOptions(expr: ts.Expression, facts: FileFacts, seen: Set<Binding>): Options {
  const node = unwrap(expr);
  if (ts.isObjectLiteralExpression(node)) return { ok: true, objects: [node] };
  if (ts.isConditionalExpression(node)) {
    const a = resolveOptions(node.whenTrue, facts, seen);
    if (!a.ok) return a;
    const b = resolveOptions(node.whenFalse, facts, seen);
    if (!b.ok) return b;
    return { ok: true, objects: [...a.objects, ...b.objects] };
  }
  if (ts.isIdentifier(node)) {
    const binding = lookup(facts, node.text, node);
    if (!binding) return { ok: false, why: `\`${node.text}\` is not declared in this file` };
    if (seen.has(binding)) return { ok: false, why: `cyclic reference to \`${node.text}\`` };
    if (binding.escaped) return { ok: false, why: `\`${node.text}\` ${binding.escaped}` };
    if (binding.assignments.length === 0) {
      return { ok: false, why: `\`${node.text}\` has no visible assignment (parameter?)` };
    }
    const next = new Set(seen).add(binding);
    const out: ts.ObjectLiteralExpression[] = [];
    for (const source of binding.assignments) {
      const r = resolveOptions(source, facts, next);
      if (!r.ok) return r;
      out.push(...r.objects);
    }
    return { ok: true, objects: out };
  }
  return { ok: false, why: `options is \`${node.getText().slice(0, 48)}\`` };
}

/**
 * THE DETECTOR. One function, used for the shipped files and for every planted control —
 * round 10 had two implementations and a comment claiming they were "the same code path";
 * they were not (the plant scanner could not follow a variable, read a `@returns:` or see a
 * `.push`), so a control could go red against a detector the real files never ran.
 */
function scanSource(source: string, file = 'planted.ts'): Site[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const facts = collectFacts(sf);
  const names = llmLocalNames(sf);
  const sites: Site[] = [];

  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node)) {
      const callee = classifyCallee(node.expression, facts, names);
      if (callee) {
        const { line } = sf.getLineAndCharacterOfPosition(node.getStart());
        const at = (framed: boolean, detail: string) =>
          sites.push({ file, line: line + 1, framed, detail });

        if (callee.kind === 'opaque') {
          at(false, `LLM call ${callee.why} — its options are not readable from the call`);
        } else if (node.arguments.length === 0) {
          at(false, 'LLM call with no options argument');
        } else {
          const opts = resolveOptions(node.arguments[0], facts, new Set());
          if (!opts.ok) at(false, `options unresolved — ${opts.why}`);
          else for (const arg of opts.objects) scoreOptions(arg, facts, at);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return sites;
}

/** Score ONE resolved options object: does every system message it carries come from the
 *  factory? Split out of the walk so a site found by any callee shape is scored identically. */
function scoreOptions(
  arg: ts.ObjectLiteralExpression,
  facts: FileFacts,
  at: (framed: boolean, detail: string) => void,
): void {
  const messages = arg.properties.find(
    (p): p is ts.PropertyAssignment | ts.ShorthandPropertyAssignment =>
      (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p))
      && ts.isIdentifier(p.name) && p.name.text === 'messages',
  );
  if (!messages) {
    // No `messages` key the walker can see — a spread options object, say. Unframed.
    at(false, 'no resolvable `messages` property on the call');
  } else {
    const value = ts.isShorthandPropertyAssignment(messages) ? messages.name : messages.initializer;
    const resolved = resolveMessages(value, facts, new Set());
    if (!resolved.ok) {
      at(false, `messages unresolved — ${resolved.why}`);
    } else {
      const systemEntries = resolved.entries.filter((obj) => {
        // A spread inside the entry hides its own keys: treat as possibly-system.
        if (obj.properties.some((p) => ts.isSpreadAssignment(p))) return true;
        const role = obj.properties.find(
          (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p)
            && ts.isIdentifier(p.name) && p.name.text === 'role',
        );
        if (!role) return true; // no role key at all: cannot rule it out.
        const roleValue = resolveStringLiteral(role.initializer, facts);
        if (roleValue === null) return true; // a role we cannot read: assume the worst.
        return roleValue === 'system';
      });
      if (systemEntries.length === 0) {
        at(true, 'no system message (every entry resolved, none is system)');
      } else {
        for (const entry of systemEntries) {
          if (entry.properties.some((p) => ts.isSpreadAssignment(p))) {
            at(false, `system entry built by spread: ${entry.getText().slice(0, 60)}`);
            continue;
          }
          const content = entry.properties.find(
            (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p)
              && ts.isIdentifier(p.name) && p.name.text === 'content',
          );
          at(
            Boolean(content && producedByFactory(content.initializer, facts)),
            content ? content.initializer.getText().slice(0, 60) : 'no content',
          );
        }
      }
    }
  }
}

function collectSites(file: string): Site[] {
  return scanSource(readFileSync(resolve(BACKEND, file), 'utf8'), file);
}

describe('every analyst LLM call receives the idea-check framing by construction', () => {
  const sites = ANALYST_FILES.flatMap(collectSites);

  /** Guards the guard. A scan that finds nothing passes for the wrong reason — which is how
   *  the round-8 policy walked 131 of 174 files and still went green. */
  it('finds every LLM call site in both analyst files', () => {
    expect(sites.length).toBeGreaterThanOrEqual(4);
    for (const file of ANALYST_FILES) {
      expect(sites.filter((s) => s.file === file).length, file).toBeGreaterThan(0);
    }
  });

  it('takes every system message from composeAnalystSystemPrompt', () => {
    const unframed = sites.filter((s) => !s.framed);
    expect(
      unframed.map((s) => `${s.file}:${s.line}  ${s.detail}`),
      unframed.length
        ? 'These calls hand the analyst model a system prompt that never saw the idea-check '
          + 'framing, or build their message list in a shape this scan cannot resolve — which '
          + 'scores the same, because "no system message found" and "no system message" are '
          + 'indistinguishable from here. Build the prompt with '
          + `${PRODUCER}(ctx, { body, dossier }) and keep the messages array resolvable.`
        : undefined,
    ).toEqual([]);
  });

  /**
   * ── CONTROLS ────────────────────────────────────────────────────────────────────────────
   * Every plant runs through `scanSource`, the SAME function the shipped files go through.
   *
   *   C-n  the shapes a round-11 critic used to walk past the round-10 scan;
   *   M-n  more of that class, found by round 11 itself;
   *   D-n  SITE DISCOVERY (round 12) — ten shapes that produced ZERO SITES against round 11,
   *        a reading indistinguishable from "this file has no LLM call". Four were measured by
   *        a round-12 critic, six more found here. Every one was GREEN.
   *   P-n  the preserving-helper whitelist (round 12) — round 11 trusted the callee's NAME, so
   *        wrapping its own headline forgery in `appendToAnalystSystemPrompt(…, '')` scored
   *        FRAMED. Both were GREEN.
   *
   * Each plant was compiled under `tsc --noEmit` against the real backend types before being
   * written down — a plant that does not compile proves nothing about a guard whose subject is
   * compiling code. The harness that does it adds the `model:` field `ChatCompleteOpts`
   * requires and hoists the two `import` lines to module scope (imports are not legal in a
   * block); neither touches a shape under test. See docs/SEED_IDENTITY_REMEDIATION.md, S10.
   */
  const RED_CONTROLS: Record<string, string> = {
    'C-1 a system message pushed after the literal (the idiom already in chat.ts)': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `const messages: ChatCompletionMessageParam[] = [{ role: 'system', content: composed }];`,
      `messages.push({ role: 'system', content: raw });`,
      `chatComplete({ messages });`,
    ].join('\n'),

    'C-2 the system entry hoisted into a const': [
      `const sys = { role: 'system' as const, content: raw };`,
      `chatComplete({ messages: [sys, { role: 'user', content: 'x' }] });`,
    ].join('\n'),

    'C-3 a same-file function that DECLARES the brand and returns a cast': [
      `function forge(): AnalystSystemPrompt { return raw as AnalystSystemPrompt; }`,
      `chatComplete({ messages: [{ role: 'system', content: forge() }] });`,
    ].join('\n'),

    'C-4 the role resolved through a same-file const': [
      `const SYSTEM_ROLE = 'system' as const;`,
      `chatComplete({ messages: [{ role: SYSTEM_ROLE, content: raw }] });`,
    ].join('\n'),

    'C-5 a system-message array spread into the literal': [
      `const head = [{ role: 'system' as const, content: raw }];`,
      `chatComplete({ messages: [...head, { role: 'user', content: 'x' }] });`,
    ].join('\n'),

    'M-1 the entry built by Object.assign instead of written as a literal': [
      `chatComplete({ messages: [Object.assign({ role: 'system' as const }, { content: raw })] });`,
    ].join('\n'),

    'M-2 the entry assembled by spreading another object': [
      `const SYS = { role: 'system' as const, content: raw };`,
      `chatComplete({ messages: [{ ...SYS }] });`,
    ].join('\n'),

    'M-3 the whole messages array behind a ternary': [
      `chatComplete({ messages: flag ? [{ role: 'system', content: raw }] : [] });`,
    ].join('\n'),

    'M-4 the messages array returned by a helper call': [
      `chatComplete({ messages: buildMessages(raw) });`,
    ].join('\n'),

    'M-5 the array handed to a mutator before the call': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `const messages = [{ role: 'system' as const, content: composed }];`,
      `decorate(messages);`,
      `chatComplete({ messages });`,
    ].join('\n'),

    'M-6 an indirect producer: a const alias for the forging cast': [
      `const forged = 'hand written' as AnalystSystemPrompt;`,
      `const alsoForged = forged;`,
      `chatCompleteStream({ messages: [{ role: 'system', content: alsoForged }] });`,
    ].join('\n'),

    'M-7 a same-file builder with one composed return and one bare-string return': [
      `function build(flag: boolean): AnalystSystemPrompt {`,
      `  if (flag) return composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `  return raw as AnalystSystemPrompt;`,
      `}`,
      `chatComplete({ messages: [{ role: 'system', content: build(true) }] });`,
    ].join('\n'),

    // The `ChatCompletionMessageParam[]` annotation is C-1's, and it is REQUIRED: without it
    // `messages` infers `content: AnalystSystemPrompt` from the composed prompt and pushing a
    // plain string is TS2322. Round 11 wrote M-8 and M-10 without it and recorded that every
    // plant compiled; neither did. The shape under test is unchanged — both still go red.
    'M-8 the entry spliced in rather than pushed': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `const messages: ChatCompletionMessageParam[] = [{ role: 'system' as const, content: composed }];`,
      `messages.splice(0, 0, { role: 'system' as const, content: raw });`,
      `chatComplete({ messages });`,
    ].join('\n'),

    'M-10 the push made through an alias for the messages array': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `const messages: ChatCompletionMessageParam[] = [{ role: 'system' as const, content: composed }];`,
      `const alias = messages;`,
      `alias.push({ role: 'system' as const, content: raw });`,
      `chatComplete({ messages });`,
    ].join('\n'),

    'M-9 the content concatenated onto a composed prompt inline': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `chatComplete({ messages: [{ role: 'system' as const, content: composed + raw }] });`,
    ].join('\n'),

    // ── D-n: SITE DISCOVERY. Round 11's fail-closed rule governed what was inside a site and
    // not whether something WAS one. Every shape below produced ZERO SITES against that scan —
    // the same reading as "this file has no LLM call" — while reaching the analyst model with
    // an unframed system prompt. D-1..D-4 are the four a round-12 critic measured; D-5..D-9
    // were found here by attacking the same conjunct from the other side.
    'D-1 the options object hoisted into a const (a routine refactor)': [
      `const opts = { model: MODEL, messages: [{ role: 'system' as const, content: raw }] };`,
      `chatComplete(opts);`,
    ].join('\n'),

    'D-2 the options built by a same-file builder': [
      `function analystOpts(s: string) { return { model: MODEL, messages: [{ role: 'system' as const, content: s }] }; }`,
      `chatComplete(analystOpts(niche));`,
    ].join('\n'),

    'D-3 the entry point imported under an alias': [
      `import { chatComplete as ask } from '../services/openai.js';`,
      `ask({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-4 a namespace callee — the call name is never an identifier': [
      `import * as llm from '../services/openai.js';`,
      `llm.chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-5 a local alias of the calling binding': [
      `const ask = chatComplete;`,
      `ask({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-6 the entry point reached through .call()': [
      `chatComplete.call(null, { model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-7 a cast in callee position': [
      `(chatComplete as typeof chatComplete)({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-11 a conditional callee': [
      `(flag ? chatComplete : chatCompleteStream)({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    'D-8 a cast on the options object': [
      `chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] } as ChatCompleteOpts);`,
    ].join('\n'),

    'D-9 the options object behind a ternary': [
      `const optsA = { model: MODEL, messages: [{ role: 'system' as const, content: raw }] };`,
      `const optsB = { model: MODEL, messages: [{ role: 'user' as const, content: 'x' }] };`,
      `chatComplete(flag ? optsA : optsB);`,
    ].join('\n'),

    'D-10 an element-access callee': [
      `const api = { chatComplete };`,
      `api['chatComplete']({ model: MODEL, messages: [{ role: 'system' as const, content: raw }] });`,
    ].join('\n'),

    // ── P-n: THE PRESERVING WHITELIST, the exact sibling of the discovery defect. Round 11
    // returned `true` on the callee's NAME without inspecting what it was handed, so that
    // round's own headline forgery — a cast inside a same-file builder — went GREEN merely by
    // being wrapped in a whitelisted helper. A laundered brand is still a forged brand.
    'P-1 a whitelisted helper wrapped around the forging cast': [
      `function forge(): AnalystSystemPrompt { return raw as AnalystSystemPrompt; }`,
      `chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: appendToAnalystSystemPrompt(forge(), '') }] });`,
    ].join('\n'),

    'P-2 the laundering nested twice over a const alias for the cast': [
      `const forged = raw as AnalystSystemPrompt;`,
      `chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: appendToAnalystSystemPrompt(appendToAnalystSystemPrompt(forged, 'a'), 'b') }] });`,
    ].join('\n'),
  };

  for (const [name, planted] of Object.entries(RED_CONTROLS)) {
    it(`goes red: ${name}`, () => {
      const found = scanSource(planted);
      expect(found.length, `${name}: the scan found no call site at all`).toBeGreaterThan(0);
      expect(
        found.map((s) => `${s.framed ? 'FRAMED' : 'unframed'} ${s.detail}`),
        `${name}: this shape reaches the analyst model with an unframed system prompt and the `
          + 'scan called it fine',
      ).toSatisfy((rows: string[]) => rows.some((r) => r.startsWith('unframed')));
    });
  }

  /**
   * ── GREEN CONTROLS ──────────────────────────────────────────────────────────────────────
   * A fail-closed DISCOVERY rule buys its safety with false positives, so the shapes it must
   * NOT fire on are pinned too. Each of these is the legitimate twin of a D-n or P-n plant
   * above — same call shape, prompt actually composed — and each must produce a site that is
   * FRAMED. The first is the shipped route's own shape and the reason `Derivation` has three
   * states: `systemPrompt = appendToAnalystSystemPrompt(systemPrompt, …)` is a fixpoint, and
   * once a preserving helper is judged on its argument that assignment resolves back into the
   * binding being resolved. A two-state walker scores it `false` and fails `chat.ts`.
   */
  const GREEN_CONTROLS: Record<string, string> = {
    'the shipped fixpoint: a composed prompt appended to in place, twice (P-1\'s twin)': [
      `let systemPrompt = composeAnalystSystemPrompt(ctx, { body: 'B', dossier: d });`,
      `systemPrompt = appendToAnalystSystemPrompt(systemPrompt, '\\n\\nWORKSPACE');`,
      `systemPrompt = appendToAnalystSystemPrompt(systemPrompt, '\\n\\nSYNTHESIS');`,
      `chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: systemPrompt }] });`,
    ].join('\n'),

    'the options object hoisted, prompt composed (D-1\'s twin)': [
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `const opts = { model: MODEL, messages: [{ role: 'system' as const, content: composed }] };`,
      `chatComplete(opts);`,
    ].join('\n'),

    'the entry point aliased on import, prompt composed (D-3\'s twin)': [
      `import { chatComplete as ask } from '../services/openai.js';`,
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `ask({ model: MODEL, messages: [{ role: 'system' as const, content: composed }] });`,
    ].join('\n'),

    'a namespace callee, prompt composed (D-4\'s twin)': [
      `import * as llm from '../services/openai.js';`,
      `const composed = composeAnalystSystemPrompt(ctx, { body: 'B' });`,
      `llm.chatComplete({ model: MODEL, messages: [{ role: 'system' as const, content: composed }] });`,
    ].join('\n'),
  };

  for (const [name, planted] of Object.entries(GREEN_CONTROLS)) {
    it(`stays green: ${name}`, () => {
      const found = scanSource(planted);
      expect(found.length, `${name}: the scan found no call site at all`).toBeGreaterThan(0);
      expect(
        found.filter((s) => !s.framed).map((s) => s.detail),
        `${name}: this is legitimate composed code and the fail-closed discovery rule failed it`,
      ).toEqual([]);
    });
  }

  it('passes a generator that composes, and one that appends to a composed prompt', () => {
    const ok = [
      `const p = composeAnalystSystemPrompt(ctx, { body: 'B', dossier: d });`,
      `const q = appendToAnalystSystemPrompt(p, '\\n\\nEXTRA');`,
      `chatComplete({ messages: [{ role: 'system', content: p }] });`,
      `chatCompleteStream({ messages: [{ role: 'system', content: q }] });`,
    ].join('\n');
    expect(scanSource(ok).every((s) => s.framed)).toBe(true);
    expect(scanSource(ok).length).toBe(2);
  });

  /** The real route's own shape: a literal, a `.map` of prior turns, and `.push`es of
   *  non-system rounds. It must stay GREEN, or the scan is unusable and gets deleted. */
  it('passes the real tool-loop shape: literal + history.map + assistant/tool pushes', () => {
    const ok = [
      `const p = composeAnalystSystemPrompt(ctx, { body: 'B', dossier: d });`,
      `const messages: ChatCompletionMessageParam[] = [`,
      `  { role: 'system', content: p },`,
      `  ...history.map((h): ChatCompletionMessageParam =>`,
      `    h.role === 'assistant' ? { role: 'assistant', content: h.content } : { role: 'user', content: h.content }),`,
      `  { role: 'user', content: message },`,
      `];`,
      `messages.push({ role: 'assistant', content: roundContent, tool_calls: [] });`,
      `messages.push({ role: 'tool', tool_call_id: id, content: fenced });`,
      `chatCompleteStream({ messages });`,
    ].join('\n');
    const sites = scanSource(ok);
    expect(sites.map((s) => s.detail)).toEqual(['p']);
    expect(sites.every((s) => s.framed)).toBe(true);
  });

  /**
   * The six shipped generators, PINNED BY SITE rather than counted. A count goes green when a
   * generator is deleted; this list goes red, and it also goes red when a seventh appears
   * (which is the moment somebody should be reading the new prompt, not the moment a
   * threshold happens to still hold).
   *
   * Two of the six — `buildG1SystemPrompt` and `buildG2SystemPrompt` — share the tool-loop
   * call site with G3 and gate 6: all four assign the same `systemPrompt` variable, and the
   * scan resolves that variable to all four builders, so the two call sites below cover four
   * generators between them. That is stated here because "4 sites, 6 generators" reads like
   * a hole otherwise.
   */
  it('pins every shipped analyst call site, and there are no others', () => {
    expect(sites.map((s) => `${s.file}:${s.line} ${s.framed ? 'framed' : 'UNFRAMED'} ${s.detail}`))
      .toEqual([
        // generateSuggestions — the follow-up chips (surface 20)
        'src/routes/chat.ts:1886 framed suggestionSystemPrompt',
        // the analyst tool loop: G1 / G2 / G3 / completed-report all reach it via `systemPrompt`
        'src/routes/chat.ts:3580 framed systemPrompt',
        'src/routes/chat.ts:3614 framed systemPrompt',
        // the mutation follow-up note (surface 21)
        'src/services/analystFollowupService.ts:161 framed systemPrompt(input.kind, ctx)',
      ]);
  });
});

/**
 * THE INVENTORY. `ANALYST_FILES` is a list, so the thing that keeps it honest cannot be the
 * same list: every backend file that can talk to the analyst model must be classified, and a
 * file in NEITHER bucket fails by name.
 *
 * Round 10 found callers with `/\bchatComplete(?:Stream)?\s*\(/`, which sees neither
 * `import { chatComplete as ask }` nor a new file driving the OpenAI SDK directly. The
 * question is now asked of the IMPORT GRAPH instead of the call spelling: model access lives
 * in exactly one module (`services/openai.ts`) plus the `openai` package itself, so a file
 * has model access iff it imports a calling binding — under any local name — or the SDK.
 * A separate assertion keeps that premise true by banning re-exports of the calling bindings,
 * which is what would otherwise let a second hop launder the import.
 *
 * CLEARED is not an exemption, it is a claim with a mechanical corroboration: a cleared file
 * must not receive the run's niche. That single fact is what makes this whole surface class
 * possible — on a `validate_idea` run `Job.niche` IS the user's raw pitch.
 */
const CLEARED_LLM_CALLERS: Record<string, string> = {
  'src/routes/suggest.ts':
    'runs BEFORE a job exists (no prisma access at all) and persists nothing.',
  'src/services/clarifyIdea.ts':
    'same pre-job path; contains no occurrence of "niche" at all.',
  'src/services/categorizationService.ts':
    'catalog path — interpolates a catalog item\'s category, never a Job row.',
  'src/services/faqGeneratorService.ts':
    'catalog path — anchors on the sub-niche/category NAME, never a Job row.',
  'src/services/founderFitService.ts':
    'candidate-scoped selection workspace; no prisma access and no "niche" identifier.',
  'src/services/selectionChallengeService.ts':
    'candidate-scoped selection workspace; no prisma access and no "niche" identifier.',
  'src/services/selectionConceptSetService.ts':
    'candidate-scoped; carries run-level wallet CLASSIFICATIONS, never the niche string.',
  'src/services/selectionFounderFitReshapeService.ts':
    'candidate-scoped selection workspace; no prisma access and no "niche" identifier.',
  'src/services/selectionIdeaNarrowingService.ts':
    'candidate-scoped selection workspace; no prisma access and no "niche" identifier.',
};

/** The one module that may call the provider, and the bindings that do the calling. */
const MODEL_ACCESS_MODULE = 'src/services/openai.ts';
const MODEL_ACCESS_BINDINGS = new Set(['chatComplete', 'chatCompleteStream']);
const RAW_SDK_PACKAGE = 'openai';

function backendSourceFiles(): string[] {
  const walk = (dir: string, out: string[] = []): string[] => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full, out);
      else if (entry.endsWith('.ts') && !entry.endsWith('.d.ts')) out.push(full);
    }
    return out;
  };
  return walk(resolve(BACKEND, 'src'))
    .map((f) => relative(BACKEND, f).split('\\').join('/'))
    .filter((f) => !f.includes('__tests__'));
}

interface ImportFact {
  /** module specifier as written */
  specifier: string;
  /** exported names brought in (propertyName when aliased), or '*' for namespace/default */
  names: string[];
  /** the LOCAL names those bindings go by in this file (what a call site actually spells) */
  locals: string[];
}

function importsOf(file: string, source?: string): ImportFact[] {
  const src = source ?? readFileSync(resolve(BACKEND, file), 'utf8');
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true);
  const out: ImportFact[] = [];
  for (const stmt of sf.statements) {
    if (ts.isImportDeclaration(stmt) && ts.isStringLiteral(stmt.moduleSpecifier)) {
      const names: string[] = [];
      const locals: string[] = [];
      const clause = stmt.importClause;
      if (!clause) continue;
      if (clause.name) { names.push('*'); locals.push(clause.name.text); }
      if (clause.namedBindings) {
        if (ts.isNamespaceImport(clause.namedBindings)) {
          names.push('*');
          locals.push(clause.namedBindings.name.text);
        } else {
          for (const el of clause.namedBindings.elements) {
            names.push((el.propertyName ?? el.name).text);
            locals.push(el.name.text);
          }
        }
      }
      out.push({ specifier: stmt.moduleSpecifier.text, names, locals });
    }
    // `export { chatComplete } from './openai.js'` — a second hop. Recorded as an import so
    // the re-export ban below can see it.
    if (ts.isExportDeclaration(stmt) && stmt.moduleSpecifier && ts.isStringLiteral(stmt.moduleSpecifier)) {
      const names: string[] = [];
      if (stmt.exportClause && ts.isNamedExports(stmt.exportClause)) {
        for (const el of stmt.exportClause.elements) names.push((el.propertyName ?? el.name).text);
      } else {
        names.push('*');
      }
      out.push({ specifier: stmt.moduleSpecifier.text, names, locals: [] });
    }
  }
  return out;
}

function resolvesToModelAccessModule(fromFile: string, specifier: string): boolean {
  if (!specifier.startsWith('.')) return false;
  const dir = dirname(resolve(BACKEND, fromFile));
  const abs = resolve(dir, specifier.replace(/\.js$/, '.ts'));
  return relative(BACKEND, abs).split('\\').join('/') === MODEL_ACCESS_MODULE;
}

/**
 * Does this file have a way to reach the provider? Asked of the IMPORT GRAPH, not of the call
 * spelling — a pure function so the escapes can be planted as controls instead of trusted.
 */
function hasModelAccess(file: string, source: string): boolean {
  if (file === MODEL_ACCESS_MODULE) return false; // the module that DEFINES access.
  // (a) the call spelling, kept as a belt: a dynamic import or a `require` would still be
  //     visible here even if the import graph missed it.
  if (/\bchatComplete(?:Stream)?\s*\(/.test(source)) return true;
  for (const imp of importsOf(file, source)) {
    // (b) the raw SDK: a new file can talk to the provider without touching openai.ts at all.
    if (imp.specifier === RAW_SDK_PACKAGE) return true;
    // (c) a calling binding under ANY local alias, plus namespace/default imports of the
    //     access module, which hide which binding is used.
    if (resolvesToModelAccessModule(file, imp.specifier)) {
      if (imp.names.some((n) => n === '*' || MODEL_ACCESS_BINDINGS.has(n))) return true;
    }
  }
  return false;
}

/**
 * G-4 — does the run's niche reach this file? Three in-file questions; the fourth (call
 * sites in OTHER files) is asked by the test, because it needs the whole tree.
 */
function nicheReachesFile(file: string, source: string): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const offenders: string[] = [];
  const walk = (node: ts.Node) => {
    // (1) reads the column off a Job-shaped value.
    if (ts.isPropertyAccessExpression(node) && node.name.text === 'niche') {
      const receiver = node.expression.getText();
      if (/\bjob\b/i.test(receiver)) offenders.push(`${file}: reads \`${receiver}.niche\``);
    }
    // (1b) touches the Job table at all — a destructured `{ niche }` off a Job row has no
    //      `.niche` access to find, so the read itself is what gets banned.
    if (
      ts.isPropertyAccessExpression(node) && node.name.text === 'job'
      && /\bprisma\b/i.test(node.expression.getText())
    ) {
      offenders.push(`${file}: reads the Job table (\`${node.getText()}\`)`);
    }
    // (2) selects the column in a prisma query.
    if (
      ts.isPropertyAssignment(node) && ts.isIdentifier(node.name) && node.name.text === 'niche'
      && node.initializer.kind === ts.SyntaxKind.TrueKeyword
    ) {
      offenders.push(`${file}: selects \`niche: true\``);
    }
    // (3) accepts it in an exported signature — "arriving as a parameter".
    if (ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
      const own = ts.canHaveModifiers(node)
        && (ts.getModifiers(node) ?? []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
      const viaVariable = node.parent && ts.isVariableDeclaration(node.parent)
        && node.parent.parent?.parent && ts.isVariableStatement(node.parent.parent.parent)
        && (ts.getModifiers(node.parent.parent.parent) ?? [])
          .some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
      if (own || viaVariable) {
        for (const param of node.parameters) {
          if (ts.isIdentifier(param.name) && param.name.text === 'niche') {
            offenders.push(`${file}: exported signature takes a \`niche\` parameter`);
          }
          if (/\bniche\s*[?]?\s*:/.test(param.type?.getText() ?? '')) {
            offenders.push(`${file}: exported signature takes an object with a \`niche\` member`);
          }
        }
      }
    }
    ts.forEachChild(node, walk);
  };
  walk(sf);
  return offenders;
}

describe('every analyst LLM caller is classified: framed, or cleared for a stated reason', () => {
  it('accounts for every file with model access in src/', () => {
    const files = backendSourceFiles();
    expect(files.length).toBeGreaterThan(50);

    const callers = files.filter(
      (f) => hasModelAccess(f, readFileSync(resolve(BACKEND, f), 'utf8')),
    );

    const classified = new Set([...ANALYST_FILES, ...Object.keys(CLEARED_LLM_CALLERS)]);
    const unclassified = callers.filter((f) => !classified.has(f));
    expect(
      unclassified,
      unclassified.length
        ? 'A new file can talk to the analyst model and is in neither bucket. Add it to '
          + 'ANALYST_FILES (and build its prompt through composeAnalystSystemPrompt), or to '
          + 'CLEARED_LLM_CALLERS with the reason it cannot claim anything about the user\'s '
          + `submitted idea:\n  ${unclassified.join('\n  ')}`
        : undefined,
    ).toEqual([]);
    // And the buckets must still describe real files: a stale entry is a claim about code
    // that no longer exists.
    for (const known of classified) {
      expect(callers, `${known} no longer has model access`).toContain(known);
    }
  });

  /**
   * The premise of the import-graph rule: model access has exactly ONE source. A re-export
   * (`export { chatComplete } from './openai.js'`, or a wrapper module re-exporting its own
   * import) would give a new file a second, unwatched door.
   */
  it('keeps model access to a single module — nobody re-exports the calling bindings', () => {
    const offenders: string[] = [];
    for (const f of backendSourceFiles()) {
      if (f === MODEL_ACCESS_MODULE) continue;
      const src = readFileSync(resolve(BACKEND, f), 'utf8');
      const sf = ts.createSourceFile(f, src, ts.ScriptTarget.Latest, true);
      for (const stmt of sf.statements) {
        if (!ts.isExportDeclaration(stmt)) continue;
        if (stmt.exportClause && ts.isNamedExports(stmt.exportClause)) {
          for (const el of stmt.exportClause.elements) {
            if (MODEL_ACCESS_BINDINGS.has((el.propertyName ?? el.name).text)) {
              offenders.push(`${f}: re-exports ${el.name.text}`);
            }
          }
        } else if (stmt.moduleSpecifier && resolvesToModelAccessModule(f, (stmt.moduleSpecifier as ts.StringLiteral).text)) {
          offenders.push(`${f}: \`export *\` from the model-access module`);
        }
      }
    }
    expect(
      offenders,
      offenders.length
        ? 'The inventory finds callers by their IMPORT of `chatComplete`/`chatCompleteStream` '
          + 'from services/openai.ts. A re-export gives a file a second door the inventory does '
          + `not watch:\n  ${offenders.join('\n  ')}`
        : undefined,
    ).toEqual([]);
  });

  /**
   * ── INVENTORY CONTROLS ────────────────────────────────────────────────────────────────
   * Round 10 found callers with `/\bchatComplete(?:Stream)?\s*\(/` over the file text. Both
   * shapes below are files that talk to the analyst model and contain no such spelling; both
   * were GREEN. They are planted here through `hasModelAccess`, the same function the sweep
   * above runs, so the sweep cannot quietly stop seeing them.
   */
  const ACCESS_CONTROLS: Record<string, { file: string; source: string; access: boolean; oldRuleSaw: boolean }> = {
    'an aliased import — the call name never appears': {
      file: 'src/services/newThing.ts',
      source: [
        `import { chatComplete as ask } from './openai.js';`,
        `export const go = () => ask({ model: 'm', messages: [] });`,
      ].join('\n'),
      access: true,
      oldRuleSaw: false,
    },
    'a namespace import of the access module': {
      file: 'src/services/newThing.ts',
      source: [
        `import * as llm from './openai.js';`,
        `export const go = () => llm.chatComplete({ model: 'm', messages: [] });`,
      ].join('\n'),
      access: true,
      // `\b` matches after the dot, so the old text rule did catch this one. Kept as a
      // control anyway: it is caught for a DIFFERENT reason now, and both must hold.
      oldRuleSaw: true,
    },
    'a new file driving the raw OpenAI SDK': {
      file: 'src/services/newThing.ts',
      source: [
        `import OpenAI from 'openai';`,
        `const client = new OpenAI({ apiKey: 'k' });`,
        `export const go = () => client.chat.completions.create({ model: 'm', messages: [] });`,
      ].join('\n'),
      access: true,
      oldRuleSaw: false,
    },
    'a wrapper module that only re-exports the binding': {
      file: 'src/services/llmDoor.ts',
      source: `export { chatComplete } from './openai.js';`,
      access: true,
      oldRuleSaw: false,
    },
    'NEGATIVE CONTROL — a file that imports only the key check': {
      file: 'src/routes/founderFit.ts',
      source: [
        `import { hasApiKeyForModel } from '../services/openai.js';`,
        `export const go = () => hasApiKeyForModel('m');`,
      ].join('\n'),
      access: false,
      oldRuleSaw: false,
    },
  };

  for (const [name, control] of Object.entries(ACCESS_CONTROLS)) {
    it(`inventory ${control.access ? 'sees' : 'ignores'}: ${name}`, () => {
      expect(hasModelAccess(control.file, control.source)).toBe(control.access);
      // …and the DELTA, measured rather than asserted in prose: what the round-10 text rule
      // saw. Three of the four access shapes were invisible to it.
      expect(
        /\bchatComplete(?:Stream)?\s*\(/.test(control.source),
        'the round-10 text rule\'s verdict on this shape has changed; re-derive the delta',
      ).toBe(control.oldRuleSaw);
    });
  }

  /**
   * G-4 — THE CORROBORATION, AND EXACTLY HOW FAR IT REACHES.
   *
   * Round 10 held cleared files to "never reads `Job.niche`" with `/\bjob\.niche\b/` inside
   * the file. A niche arriving as a PARAMETER, or read one file away and passed in, was
   * invisible — the check could not keep the property it was named after. It now asks three
   * questions instead of one, and the third one leaves the file:
   *
   *   1. does the file read the niche column itself (`x.niche`, `niche: true` in a select)?
   *   2. does any EXPORTED signature accept it (a parameter named `niche`, or an object type
   *      with a `niche` member)? — "arriving as a parameter";
   *   3. does any call site anywhere in `src/` pass something spelled `niche` into one of the
   *      file's exported bindings? — "read one file away", at depth one.
   *
   * THE BOUNDARY, written down rather than implied: this is a NAME-based check at import
   * depth one. It does not catch a niche renamed on the way in (`const subject = job.niche;
   * f(subject)`), nor one passed through an intermediate module, nor one embedded in a
   * bigger object under a different key. Those remain a hand audit — all nine entries were
   * audited by hand when they were written, and this test's job is to make a REGRESSION
   * loud, not to prove the clearance from scratch. When a cleared file's surface changes,
   * re-audit it; do not read a green here as the audit.
   */
  it('holds every cleared caller to the fact that clears it — the niche never reaches it', () => {
    const clearedFiles = Object.keys(CLEARED_LLM_CALLERS);
    let consumersSeen = 0;
    const offenders = clearedFiles.flatMap(
      (f) => nicheReachesFile(f, readFileSync(resolve(BACKEND, f), 'utf8')),
    );

    // (4) depth-one call sites: does anyone pass something spelled `niche` into a cleared
    //     file's exported bindings? This is the half that leaves the file — the half the
    //     round-10 in-file regex could not have.
    for (const consumer of backendSourceFiles()) {
      if (clearedFiles.includes(consumer)) continue;
      const src = readFileSync(resolve(BACKEND, consumer), 'utf8');
      const sf = ts.createSourceFile(consumer, src, ts.ScriptTarget.Latest, true);
      const importedFrom = new Map<string, string>(); // LOCAL name -> cleared file
      for (const imp of importsOf(consumer, src)) {
        if (!imp.specifier.startsWith('.')) continue;
        const abs = resolve(dirname(resolve(BACKEND, consumer)), imp.specifier.replace(/\.js$/, '.ts'));
        const rel = relative(BACKEND, abs).split('\\').join('/');
        if (!clearedFiles.includes(rel)) continue;
        for (const local of imp.locals) importedFrom.set(local, rel);
      }
      if (importedFrom.size === 0) continue;
      consumersSeen += 1;
      const walk = (node: ts.Node) => {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
          const target = importedFrom.get(node.expression.text);
          if (target) {
            for (const arg of node.arguments) {
              if (/\bniche\b/i.test(arg.getText())) {
                offenders.push(
                  `${consumer}: passes a \`niche\` into ${node.expression.text}() from ${target}`,
                );
              }
            }
          }
        }
        ts.forEachChild(node, walk);
      };
      walk(sf);
    }

    // Guards the guard: the cross-file half is worthless if it walked nothing. Twelve files
    // import a cleared service today; the floor is deliberately low, the point is non-zero.
    expect(consumersSeen, 'no file imports a cleared caller — the depth-one half ran on nothing')
      .toBeGreaterThanOrEqual(5);

    const unique = [...new Set(offenders)];
    expect(
      unique,
      unique.length
        ? 'These files were cleared because the run\'s niche never reaches them — which on a '
          + '`validate_idea` run IS the user\'s raw pitch. It does now, so the clearance no '
          + `longer holds:\n  ${unique.join('\n  ')}`
        : undefined,
    ).toEqual([]);
  });

  /**
   * Controls for the corroboration itself. Round 10's version — `/\bjob\.niche\b/` over the
   * file text — is GREEN on all four of these, which is the whole finding.
   */
  const NICHE_REACH_CONTROLS: Record<string, { source: string; caught: boolean; oldRuleSaw: boolean }> = {
    'the niche arrives as a parameter': {
      source: `export function summarise(niche: string): string { return niche; }`,
      caught: true,
      oldRuleSaw: false,
    },
    'the niche arrives inside an options object': {
      source: `export function summarise(opts: { jobId: string; niche: string }): string { return opts.jobId; }`,
      caught: true,
      oldRuleSaw: false,
    },
    'the file reads the Job table itself': {
      source: `export async function go() { return prisma.job.findUnique({ where: { id: 'x' } }); }`,
      caught: true,
      oldRuleSaw: false,
    },
    'the file selects the column': {
      source: `export async function go() { return prisma.something.findMany({ select: { niche: true } }); }`,
      caught: true,
      oldRuleSaw: false,
    },
    'the round-10 shape still fires': {
      source: `export function go(job: { niche: string }) { return job.niche; }`,
      caught: true,
      oldRuleSaw: true,
    },
    'NEGATIVE CONTROL — a catalog item\'s own niche name': {
      source: `const line = \`Niche: \${item.niche}\`;\nexport const go = () => line;`,
      caught: false,
      oldRuleSaw: false,
    },
  };

  for (const [name, control] of Object.entries(NICHE_REACH_CONTROLS)) {
    it(`clearance check ${control.caught ? 'catches' : 'allows'}: ${name}`, () => {
      const found = nicheReachesFile('src/services/cleared.ts', control.source);
      expect(found.length > 0, found.join(' | ')).toBe(control.caught);
      expect(
        /\bjob\.niche\b/.test(control.source),
        'the round-10 rule\'s verdict on this shape has changed; re-derive the delta',
      ).toBe(control.oldRuleSaw);
    });
  }
});
