let token = '';
export async function initSession() {
  const response = await fetch('/api/session', {cache: 'no-store'});
  if (!response.ok) throw new Error('无法连接本机程序');
  token = (await response.json()).token;
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.method && options.method !== 'GET') headers.set('x-editor-token', token);
  const response = await fetch('/api' + path, {...options, headers});
  if (!response.ok) {
    let message = `本机请求失败 (${response.status})`;
    try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail; } catch { /* preserve HTTP error */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const jsonRequest = (value: unknown,method:'PUT'|'POST'='PUT'): RequestInit => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)});
export async function upload(file: File) {
  if (file.size > 10_000_000) throw new Error('图片不能超过 10 MB');
  const form = new FormData(); form.append('file', file);
  return api<import('../domain/project').Asset>('/assets', {method: 'POST', body: form});
}
