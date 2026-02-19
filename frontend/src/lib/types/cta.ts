export type CtaIconName = 'none' | 'arrow-right' | 'scroll-text' | 'file-text' | 'sparkles' | 'external-link';

export interface CtaConfig {
  text: string;
  visible: boolean;
  url: string;
  icon?: CtaIconName;
}
