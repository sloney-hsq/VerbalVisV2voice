export const DEFAULT_CHART_HEIGHT = 270;
export const MAX_CHART_HEIGHT = 290;

/**
 * All dashboard views occupy exactly one grid cell. This helper only adjusts
 * the internal plotting height when a categorical bar chart needs enough
 * vertical room for its labels; it never changes grid span or view priority.
 */
export function chartHeightForView(view) {
  const rows = Array.isArray(view?.data) ? view.data.length : 0;
  const isCategoryBar = (
    view?.chart_type === "bar" &&
    view?.x_field === "product_category"
  );

  if (!isCategoryBar) return DEFAULT_CHART_HEIGHT;

  const estimatedHeight = 62 + rows * 15;
  return Math.min(
    MAX_CHART_HEIGHT,
    Math.max(DEFAULT_CHART_HEIGHT, estimatedHeight),
  );
}
