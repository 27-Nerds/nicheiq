import type { SolutionPreview } from "$lib/types/job";
import type { RuledOutFinding } from "$lib/types/report";

export interface IdeaReference {
  id: string;
  label: string;
  kind: "ranked" | "ruled-out";
  solutionName?: string;
  ruledOutIndex?: number;
  aliases: string[];
}

export type IdeaReferenceSegment =
  | { text: string; reference?: undefined }
  | { text: string; reference: IdeaReference };

const GENERIC_SUFFIXES = new Set([
  "app", "application", "dashboard", "generator", "platform", "service", "tool",
]);

function words(value: string): string[] {
  return value.match(/[\p{L}\p{N}]+/gu) ?? [];
}

function normalized(value: string): string {
  return value.toLocaleLowerCase();
}

function addAlias(target: Set<string>, value: string): void {
  const alias = value.trim();
  if (alias.replace(/[^\p{L}\p{N}]/gu, "").length >= 4) target.add(alias);
}

/** Canonical name plus conservative aliases commonly emitted by the analyst. */
export function aliasesForIdeaName(name: string): string[] {
  const aliases = new Set<string>();
  addAlias(aliases, name);

  const head = name.split(/[:—–]/, 1)[0]?.trim();
  if (head && head !== name) addAlias(aliases, head);

  const withoutTrailingQualifier = name.replace(/\s*\([^)]*\)\s*$/, "").trim();
  if (withoutTrailingQualifier && withoutTrailingQualifier !== name) addAlias(aliases, withoutTrailingQualifier);

  const allWords = words(name);
  const trimmedWords = [...allWords];
  while (trimmedWords.length > 1 && GENERIC_SUFFIXES.has(normalized(trimmedWords.at(-1)!))) {
    trimmedWords.pop();
  }

  for (const parts of [allWords, trimmedWords]) {
    if (!parts.length) continue;
    addAlias(aliases, parts.join(""));
    addAlias(aliases, parts.join(" "));
    for (let prefixLength = 2; prefixLength <= Math.min(3, parts.length - 1); prefixLength += 1) {
      const prefix = parts.slice(0, prefixLength).map((part) => part[0]).join("");
      addAlias(aliases, `${prefix}${parts.slice(prefixLength).join("")}`);
    }
  }

  return [...aliases];
}

export function buildIdeaReferences(
  solutions: readonly SolutionPreview[],
  ruledOut: readonly RuledOutFinding[],
): IdeaReference[] {
  const references: IdeaReference[] = solutions.map((solution) => ({
    id: `ranked:${solution.solution_name}`,
    label: solution.solution_name,
    kind: "ranked",
    solutionName: solution.solution_name,
    aliases: [
      ...aliasesForIdeaName(solution.solution_name),
      ...(solution.headline ? aliasesForIdeaName(solution.headline) : []),
    ],
  }));

  const rankedNames = new Set(solutions.map((solution) => normalized(solution.solution_name)));
  ruledOut.forEach((finding, index) => {
    const label = (finding.idea_name || finding.idea?.solution_name || "").trim();
    if (!label || rankedNames.has(normalized(label))) return;
    references.push({
      id: `ruled-out:${index}:${label}`,
      label,
      kind: "ruled-out",
      ruledOutIndex: index,
      aliases: aliasesForIdeaName(label),
    });
  });

  // Never link an alias that could open two different ideas.
  const aliasCounts = new Map<string, number>();
  for (const reference of references) {
    for (const alias of new Set(reference.aliases.map(normalized))) {
      aliasCounts.set(alias, (aliasCounts.get(alias) ?? 0) + 1);
    }
  }
  return references.map((reference) => ({
    ...reference,
    aliases: reference.aliases.filter((alias) => aliasCounts.get(normalized(alias)) === 1),
  }));
}

function isWordCharacter(value: string | undefined): boolean {
  return !!value && /[\p{L}\p{N}]/u.test(value);
}

export function matchIdeaReferences(
  text: string,
  references: readonly IdeaReference[],
): IdeaReferenceSegment[] {
  if (!text || !references.length) return [{ text }];

  const candidates = references.flatMap((reference) =>
    reference.aliases.map((alias) => ({ alias, normalized: normalized(alias), reference })),
  );
  const haystack = normalized(text);
  const segments: IdeaReferenceSegment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    let best: { start: number; end: number; reference: IdeaReference } | null = null;
    for (const candidate of candidates) {
      let start = haystack.indexOf(candidate.normalized, cursor);
      while (start >= 0) {
        const end = start + candidate.alias.length;
        if (!isWordCharacter(text[start - 1]) && !isWordCharacter(text[end])) {
          if (!best || start < best.start || (start === best.start && end > best.end)) {
            best = { start, end, reference: candidate.reference };
          }
          break;
        }
        start = haystack.indexOf(candidate.normalized, start + 1);
      }
    }

    if (!best) {
      segments.push({ text: text.slice(cursor) });
      break;
    }
    if (best.start > cursor) segments.push({ text: text.slice(cursor, best.start) });
    segments.push({ text: text.slice(best.start, best.end), reference: best.reference });
    cursor = best.end;
  }

  return segments;
}
