export type CompanyGroupJob = {
  id: string;
  company: string;
  company_key?: string;
  companyKey?: string;
};

export type CompanyJobGroup<T extends CompanyGroupJob> = {
  key: string;
  company: string;
  jobs: T[];
};

function normalizedCompanyName(company: string): string {
  return String(company || "").trim().replace(/\s+/g, " ").toLowerCase();
}

export function groupJobsByCompany<T extends CompanyGroupJob>(jobs: T[]): CompanyJobGroup<T>[] {
  const groups = new Map<string, CompanyJobGroup<T>>();

  for (const job of jobs) {
    const companyKey = String(job.company_key || job.companyKey || "").trim();
    const nameKey = normalizedCompanyName(job.company);
    const key = companyKey ? `key:${companyKey}` : `name:${nameKey}`;
    const existing = groups.get(key);
    if (existing) {
      existing.jobs.push(job);
      continue;
    }
    groups.set(key, {
      key,
      company: String(job.company || "").trim() || "未标注公司",
      jobs: [job],
    });
  }

  return [...groups.values()];
}
