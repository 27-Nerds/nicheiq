/** Tolerant readers for the thesis partition on a preview report.
 *
 * The selection screen used to present N ideas as N independent opportunities. In
 * practice they collapse into a handful of buyer-job families, and some validated
 * jobs end up with no surviving idea at all. `idea_theses` carries that partition
 * so the UI can say "five jobs examined; two uncovered; three theses" instead of
 * listing twelve padded options.
 *
 * The shapes live in `$lib/types/report.ts` (they mirror the Python models) and are
 * re-exported here — this module owns only the RUNTIME parsing. The preview report
 * arrives untyped (raw JSON off the API / an older checkpoint), so a malformed
 * entry must be dropped rather than crash the ranked list.
 */

import { buyerFacingIdeaProse } from "$lib/selection/buyerFacingResearchProse";
import type {
	IdeaThesis,
	IdeaThesisPartition,
	ThesisFatalAssumption,
	ThesisMember,
	UncoveredFamily,
} from "./report";

export type {
	IdeaThesis,
	IdeaThesisPartition,
	ThesisFatalAssumption,
	ThesisMember,
	UncoveredFamily,
};

export type ThesisIncumbentStatus = IdeaThesis["incumbent_status"];
type UncoveredReason = UncoveredFamily["reason"];

const INCUMBENT_STATUSES: ThesisIncumbentStatus[] = ["occupied", "partial", "open", "unknown"];
const UNCOVERED_REASONS: UncoveredReason[] = [
	"no_cell_allocated",
	"no_surviving_idea",
	"unknown",
];

function record(value: unknown): Record<string, unknown> | null {
	return value && typeof value === "object" && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: null;
}

function stringList(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return value
		.filter((entry): entry is string => typeof entry === "string")
		.map((entry) => entry.trim())
		.filter(Boolean);
}

function text(value: unknown): string | null {
	return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** Non-optional string fields on the contract: absent reads as empty, never null, so
 *  callers can treat the parsed shape as the real `IdeaThesis`. */
function str(value: unknown): string {
	return text(value) ?? "";
}

/** `members: [{name, winning_angle, ...}]` is the contract. A producer that only ever
 *  emitted the flat name list is upgraded in place so both render identically. */
function readMembers(raw: Record<string, unknown>): ThesisMember[] {
	if (Array.isArray(raw.members)) {
		return raw.members.flatMap((entry) => {
			const member = record(entry);
			const name = member ? text(member.name) : null;
			if (!name) return [];
			return [{
				name,
				winning_angle: member ? text(member.winning_angle) : null,
				idea_tier: text(member?.idea_tier) ?? undefined,
				source_frame: text(member?.source_frame) ?? undefined,
			}];
		});
	}
	return stringList(raw.member_idea_names).map((name) => ({ name }));
}

/** The assumption is PIPELINE PROSE, and it is the densest pocket of pipeline vocabulary in
 *  the whole partition: 132 of the corpus's capitalised "Cold start" instances are in this
 *  one field, e.g. "Cold start: the product has no data until a customer supplies it — …".
 *  It rendered raw at `SelectionWorkbench.svelte:3685` through round 6 while a unit test
 *  asserted a rewrite that no render path performed. Sanitising in the READER covers the
 *  workbench, the shared-discovery view and the job page at once, and keeps the value used
 *  as the `{#each}` key identical to the value on screen.
 *
 *  `idea_name` is deliberately NOT sanitised — it is a proper name (see
 *  `SelectionWorkbench.svelte:2114`), and `source_field` is a machine token. */
function readFatalAssumptions(raw: unknown): ThesisFatalAssumption[] {
	if (!Array.isArray(raw)) return [];
	return raw.flatMap((entry) => {
		const item = record(entry);
		if (!item) return [];
		// `text` was never the field name the pipeline emits; accepted only so a
		// hand-rolled or legacy payload degrades to a rendered chip, not a blank one.
		const assumption = text(item.assumption) ?? text(item.text);
		if (!assumption) return [];
		return [{
			idea_name: str(item.idea_name),
			source_field: str(item.source_field),
			assumption: buyerFacingIdeaProse(assumption) || assumption,
		}];
	});
}

function readThesis(entry: unknown): IdeaThesis | null {
	const raw = record(entry);
	if (!raw) return null;
	const familyId = text(raw.family_id);
	const label = text(raw.display_label);
	if (!familyId || !label) return null;
	const status = text(raw.incumbent_status)?.toLowerCase();
	return {
		family_id: familyId,
		display_label: label,
		buyer: str(raw.buyer),
		triggering_job: str(raw.triggering_job),
		economic_outcome: str(raw.economic_outcome),
		members: readMembers(raw),
		lead_idea_name: str(raw.lead_idea_name),
		incumbent_status: INCUMBENT_STATUSES.includes(status as ThesisIncumbentStatus)
			? (status as ThesisIncumbentStatus)
			: "unknown",
		incumbent_vendors: stringList(raw.incumbent_vendors),
		fatal_assumptions: readFatalAssumptions(raw.fatal_assumptions),
	};
}

/** The partition object off a preview report. `idea_theses` is an OBJECT
 *  (`{family_source, theses[], uncovered_families[], unassigned[]}`); a bare array is
 *  tolerated as the thesis list alone, with uncovered families read from the
 *  top-level field an array-shaped producer would have to put them in.
 *
 *  `unassigned` needs no reader: those ideas simply match no family, and the
 *  workbench's family lookup drops them into its "Not yet grouped" bucket. */
function readPartition(report: unknown): { theses: unknown[]; uncovered: unknown[] } {
	const raw = (report as { idea_theses?: unknown } | null | undefined)?.idea_theses;
	if (Array.isArray(raw)) {
		const legacyUncovered = (report as { uncovered_families?: unknown } | null | undefined)
			?.uncovered_families;
		return { theses: raw, uncovered: Array.isArray(legacyUncovered) ? legacyUncovered : [] };
	}
	const partition = record(raw);
	if (!partition) return { theses: [], uncovered: [] };
	return {
		theses: Array.isArray(partition.theses) ? partition.theses : [],
		uncovered: Array.isArray(partition.uncovered_families) ? partition.uncovered_families : [],
	};
}

/** Reads the thesis partition off a preview report that may predate the contract.
 *  Anything malformed is dropped rather than rendered — an absent partition falls
 *  back to the flat ranked list. */
export function readIdeaTheses(report: unknown): IdeaThesis[] {
	return readPartition(report).theses.flatMap((entry) => {
		const thesis = readThesis(entry);
		return thesis ? [thesis] : [];
	});
}

/** Validated buyer jobs that no surviving idea addresses. Nested under the partition,
 *  NOT a top-level report field. */
export function readUncoveredFamilies(report: unknown): UncoveredFamily[] {
	return readPartition(report).uncovered.flatMap((entry) => {
		const raw = record(entry);
		if (!raw) return [];
		const familyId = text(raw.family_id);
		const label = text(raw.display_label);
		if (!familyId || !label) return [];
		const reason = text(raw.reason);
		return [{
			family_id: familyId,
			display_label: label,
			member_pain_ids: stringList(raw.member_pain_ids),
			reason: UNCOVERED_REASONS.includes(reason as UncoveredReason)
				? (reason as UncoveredReason)
				: "unknown",
			reason_detail: text(raw.reason_detail) ?? undefined,
		}];
	});
}
