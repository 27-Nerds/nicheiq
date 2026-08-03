/**
 * Error Translator
 *
 * Translates classified error codes into user-friendly messages and guidance.
 * Used to transform technical errors into actionable information for users.
 */

export type ErrorCode =
  | 'RATE_LIMIT'
  | 'PROVIDER_BILLING_ERROR'
  | 'API_AUTH_ERROR'
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'VALIDATION_ERROR'
  | 'WORKER_CRASH'
  | 'SERVICE_UNAVAILABLE'
  | 'INTERNAL_ERROR';

export type ErrorSeverity = 'info' | 'warning' | 'error';

export interface TranslatedError {
  code: ErrorCode;
  severity: ErrorSeverity;
  userMessage: string;
  actionableGuidance: string;
  retryDelayMinutes?: number;
  rawMessage?: string;
}

interface ErrorTranslation {
  severity: ErrorSeverity;
  userMessage: string;
  actionableGuidance: string;
  retryDelayMinutes?: number;
}

const ERROR_TRANSLATIONS: Record<ErrorCode, ErrorTranslation> = {
  RATE_LIMIT: {
    severity: 'warning',
    userMessage: 'Service temporarily busy',
    actionableGuidance: 'Our research services are experiencing high demand. Please wait a few minutes, then click "Resume" to continue your research.',
    retryDelayMinutes: 5,
  },
  PROVIDER_BILLING_ERROR: {
    severity: 'error',
    userMessage: 'Research provider account unavailable',
    actionableGuidance: 'One of our AI research providers cannot accept more work because its service account needs attention. Your progress is saved; contact support or resume after the provider account is restored.',
  },
  API_AUTH_ERROR: {
    severity: 'warning',
    userMessage: 'Service access issue',
    actionableGuidance: 'There was a temporary issue accessing one of our research services. This usually resolves on its own. Try resuming in 10-15 minutes.',
    retryDelayMinutes: 15,
  },
  NETWORK_ERROR: {
    severity: 'warning',
    userMessage: 'Connection issue',
    actionableGuidance: 'A temporary connection issue occurred. Click "Resume" to continue your research from where it left off.',
  },
  TIMEOUT: {
    severity: 'warning',
    userMessage: 'Research taking longer than expected',
    actionableGuidance: 'The research is taking longer than usual. Consider narrowing your niche to be more specific, or try resuming to continue.',
  },
  VALIDATION_ERROR: {
    severity: 'info',
    userMessage: 'Data processing issue',
    actionableGuidance: 'There was an issue processing the research data. Try resuming, or consider using a more specific niche description.',
  },
  WORKER_CRASH: {
    severity: 'info',
    userMessage: 'Processing interrupted',
    actionableGuidance: 'Your research was interrupted but your progress is saved. Click "Resume" to continue from the last checkpoint.',
  },
  SERVICE_UNAVAILABLE: {
    severity: 'warning',
    userMessage: 'Service temporarily unavailable',
    actionableGuidance: 'One of the research services is temporarily down. Please try again in a few minutes.',
    retryDelayMinutes: 10,
  },
  INTERNAL_ERROR: {
    severity: 'error',
    userMessage: 'Something went wrong',
    actionableGuidance: 'An unexpected error occurred. Try resuming your research. If the problem persists, please contact support.',
  },
};

/**
 * Translate an error code into user-friendly message and guidance.
 *
 * @param code - The classified error code
 * @param rawMessage - Optional raw error message for debugging
 * @returns TranslatedError with user-friendly content
 */
export function translateError(code: string, rawMessage?: string): TranslatedError {
  const normalizedCode = (code?.toUpperCase() || 'INTERNAL_ERROR') as ErrorCode;
  const translation = ERROR_TRANSLATIONS[normalizedCode] || ERROR_TRANSLATIONS.INTERNAL_ERROR;

  return {
    code: normalizedCode,
    severity: translation.severity,
    userMessage: translation.userMessage,
    actionableGuidance: translation.actionableGuidance,
    retryDelayMinutes: translation.retryDelayMinutes,
    rawMessage,
  };
}

/**
 * Build complete error details for storage and API response.
 *
 * @param errorCode - The classified error code from worker
 * @param errorDetails - Raw error details from worker
 * @returns Complete error details object with translations
 */
export function buildErrorDetails(
  errorCode: string | undefined | null,
  errorDetails: Record<string, any> | undefined | null
): TranslatedError | null {
  if (!errorCode && !errorDetails) {
    return null;
  }

  const code = errorCode || errorDetails?.code || 'INTERNAL_ERROR';
  const rawMessage = errorDetails?.rawMessage || null;

  return translateError(code, rawMessage);
}
