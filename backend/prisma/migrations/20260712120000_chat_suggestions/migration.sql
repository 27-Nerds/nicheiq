-- Follow-up chips the analyst proposed for a turn (string[]); null → client falls
-- back to deterministic, state-derived suggestions.
ALTER TABLE "ChatMessage" ADD COLUMN "suggestionsJson" JSONB;
