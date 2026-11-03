const BASE = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  constructor(code, message, status) { super(message); this.code = code; this.status = status; }
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new ApiError('network', 'Cannot reach the backend. Start it with "python app.py" in the backend folder (see README).', 0);
  }
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON response */ }
  if (!res.ok || !body || body.ok !== true) {
    throw new ApiError(body?.error?.code || 'http_error', body?.error?.message || `The request failed (HTTP ${res.status}).`, res.status);
  }
  return body.data;
}

export const getHealth = () => request('/api/health');
export const getMethodology = () => request('/api/methodology');
export const analyzeUrl = (url) => request('/api/analyze-url', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
});
export const searchResearchVideos = (query) => request('/api/research/videos', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(query),
});
export const analyzeCsv = (file, threshold) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('similarity_threshold', String(threshold));
  return request('/api/analyze-csv', { method: 'POST', body: fd });
};
