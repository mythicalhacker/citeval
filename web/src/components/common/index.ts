/**
 * The citeval design system — accessible, token-driven primitives shared by every view.
 * This barrel is ADDITIVE-ONLY after W1-FE-SHELL hands off: W2 view sessions import from here and
 * may add new primitives, but must not break these public component contracts.
 */
export { Masthead, HEADLINE_STATS } from './Masthead';
export type { MastheadProps, HeadlineStat } from './Masthead';

export { Stat } from './Stat';
export type { StatProps } from './Stat';

export { Stepper } from './Stepper';
export type { StepperProps } from './Stepper';

export { CostChip } from './CostChip';
export type { CostChipProps } from './CostChip';

export { ConfidenceChip } from './ConfidenceChip';
export type { ConfidenceChipProps } from './ConfidenceChip';

export { ConfidenceGauge } from './ConfidenceGauge';
export type { ConfidenceGaugeProps } from './ConfidenceGauge';

export { GateBadge, gateFiredFromOverall } from './GateBadge';
export type { GateBadgeProps } from './GateBadge';

export { DebateCard } from './DebateCard';
export type { DebateCardProps } from './DebateCard';

export { ProvenanceBadge } from './ProvenanceBadge';
export type { ProvenanceBadgeProps } from './ProvenanceBadge';

export { AxisScale, GradeBadge } from './AxisScale';
export type { AxisScaleProps, GradeBadgeProps } from './AxisScale';
