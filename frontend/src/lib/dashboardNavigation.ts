export type JobQualityFilter = "" | "missing_jd" | "low_quality_jd" | "suspected_expired" | "blacklisted" | "duplicates" | "risk_jobs" | "ai_feedback_needs_revision" | "missing_business_name" | "no_rankings";

export type DashboardNavigation = {
  page: string;
  jobs?: {
    qualityFilter?: JobQualityFilter;
    applicationStatus?: string;
    decisionStatus?: string;
    scopeLabel?: string;
    selectedOnly?: boolean;
  };
};

const NAVIGATION_KEY = "boss-dashboard-navigation";

export function setDashboardNavigation(intent: DashboardNavigation): void {
  window.sessionStorage.setItem(NAVIGATION_KEY, JSON.stringify(intent));
}

export function resolveDashboardQualityFilter(key: string): JobQualityFilter {
  const filters: Record<string, JobQualityFilter> = {
    missing_jd: "missing_jd",
    duplicate_jobs: "duplicates",
    suspected_expired: "suspected_expired",
    blacklisted: "blacklisted",
    missing_business_name: "missing_business_name",
    low_quality_jd: "low_quality_jd",
    no_rankings: "no_rankings",
    risk_jobs: "risk_jobs",
    ai_feedback_needs_revision: "ai_feedback_needs_revision",
  };
  return filters[key] || "";
}

export function consumeDashboardNavigation(page: string): DashboardNavigation | null {
  try {
    const raw = window.sessionStorage.getItem(NAVIGATION_KEY);
    const intent = raw ? JSON.parse(raw) as DashboardNavigation : null;
    if (!intent || intent.page !== page) return null;
    window.sessionStorage.removeItem(NAVIGATION_KEY);
    return intent;
  } catch {
    window.sessionStorage.removeItem(NAVIGATION_KEY);
    return null;
  }
}
