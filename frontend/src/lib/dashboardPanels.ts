export type DashboardPanelConfig<T extends string> = {
  order: T[];
  hidden: T[];
};

export function ensureDashboardPanelVisible<T extends string>(
  config: DashboardPanelConfig<T>,
  key: T,
): DashboardPanelConfig<T> {
  const order = config.order.includes(key) ? config.order : [...config.order, key];
  return {
    order,
    hidden: config.hidden.filter(item => item !== key),
  };
}
