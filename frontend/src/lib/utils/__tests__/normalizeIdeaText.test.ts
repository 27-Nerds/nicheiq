import { describe, expect, it } from "vitest";
import { normalizeIdeaText } from "../normalizeIdeaText";

// Built from code points (not pasted literals) so the exact input characters
// are unambiguous - several are zero-width and invisible in a diff.
const chr = (codePoint: number) => String.fromCharCode(codePoint);
const LEFT_SINGLE_QUOTE = chr(0x2018);
const RIGHT_SINGLE_QUOTE = chr(0x2019);
const SINGLE_LOW9_QUOTE = chr(0x201a);
const SINGLE_HIGH_REVERSED_QUOTE = chr(0x201b);
const LEFT_DOUBLE_QUOTE = chr(0x201c);
const RIGHT_DOUBLE_QUOTE = chr(0x201d);
const DOUBLE_LOW9_QUOTE = chr(0x201e);
const DOUBLE_HIGH_REVERSED_QUOTE = chr(0x201f);
const EN_DASH = chr(0x2013);
const EM_DASH = chr(0x2014);
const MINUS_SIGN = chr(0x2212);
const ZERO_WIDTH_SPACE = chr(0x200b);
const ZERO_WIDTH_NON_JOINER = chr(0x200c);
const ZERO_WIDTH_JOINER = chr(0x200d);
const WORD_JOINER = chr(0x2060);
const BOM = chr(0xfeff);

describe("normalizeIdeaText", () => {
  it("folds curly apostrophe variants to a straight apostrophe", () => {
    expect(normalizeIdeaText(`the shop${RIGHT_SINGLE_QUOTE}s owner`)).toBe("the shop's owner");
    expect(normalizeIdeaText(`${LEFT_SINGLE_QUOTE}quoted${RIGHT_SINGLE_QUOTE}`)).toBe("'quoted'");
    expect(normalizeIdeaText(`low${SINGLE_LOW9_QUOTE}high${SINGLE_HIGH_REVERSED_QUOTE}`)).toBe("low'high'");
  });

  it("folds curly double-quote variants to a straight double quote", () => {
    expect(normalizeIdeaText(`${LEFT_DOUBLE_QUOTE}quoted${RIGHT_DOUBLE_QUOTE}`)).toBe('"quoted"');
    expect(normalizeIdeaText(`low${DOUBLE_LOW9_QUOTE}high${DOUBLE_HIGH_REVERSED_QUOTE}`)).toBe('low"high"');
  });

  it("folds en dash, em dash, and minus sign to a hyphen", () => {
    expect(normalizeIdeaText(`10${EN_DASH}20 clients`)).toBe("10-20 clients");
    expect(normalizeIdeaText(`invoices ${EM_DASH} chased manually`)).toBe("invoices - chased manually");
    expect(normalizeIdeaText(`${MINUS_SIGN}5 minutes`)).toBe("-5 minutes");
  });

  it("strips zero-width characters entirely", () => {
    const withZeroWidth =
      `a${ZERO_WIDTH_SPACE}pp for${ZERO_WIDTH_NON_JOINER} freelancers${ZERO_WIDTH_JOINER}` +
      `${WORD_JOINER}${BOM}`;
    expect(normalizeIdeaText(withZeroWidth)).toBe("app for freelancers");
  });

  it("leaves already-ASCII text unchanged", () => {
    const plain = "A Chrome extension for wedding photographers who miss invoice deadlines.";
    expect(normalizeIdeaText(plain)).toBe(plain);
  });

  it("normalizes multiple variants in a single pass", () => {
    const input = `${LEFT_DOUBLE_QUOTE}It${RIGHT_SINGLE_QUOTE}s a 5${EN_DASH}minute fix${RIGHT_DOUBLE_QUOTE}`;
    expect(normalizeIdeaText(input)).toBe(`"It's a 5-minute fix"`);
  });
});
