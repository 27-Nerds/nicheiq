import OpenAI from 'openai';
import { CONFIG } from '../config.js';

/**
 * Shared OpenAI client instance.
 * Reuses the same client across all services.
 */
export const openai = new OpenAI({
  apiKey: CONFIG.openaiApiKey,
});
