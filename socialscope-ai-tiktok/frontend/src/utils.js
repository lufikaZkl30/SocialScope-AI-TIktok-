export const nf = new Intl.NumberFormat('en-US');
export const pct = (v, d = 1) => `${Number(v).toFixed(d)}%`;
export const COLORS = { positive: '#22D3EE', neutral: '#7C8AB0', negative: '#FB7185', promo: '#A78BFA', grid: '#26345E' };

// Spreadsheet apps run cells beginning with = + - @ as formulas; prefix them so exports are safe to open.
const cell = (v) => {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
};
export const toCsv = (rows) => rows.map((r) => r.map(cell).join(',')).join('\r\n');

export function download(filename, text, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob(['\ufeff' + text], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const fmtDate = (iso) => new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC';
