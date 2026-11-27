/** Định dạng số cho UI: giá trị Backend không có (null) hiển thị "—" thay vì số giả. */
export const f = (v: number | null | undefined, digits = 2, suffix = ''): string =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : `${v.toFixed(digits)}${suffix}`;

export const n = (v: number | null | undefined, suffix = ''): string =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : `${v}${suffix}`;
