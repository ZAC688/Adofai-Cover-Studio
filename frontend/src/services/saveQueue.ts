export type SaveStatus = { kind: 'saved' | 'saving' | 'error'; message: string };

/** Serialize snapshots and acknowledge exactly the version that reached disk. */
export class SaveQueue<T> {
  revision: number;
  private sequence = 0;
  private savedSequence = 0;
  private latest: T | null = null;
  private inflight: Promise<void> | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  constructor(revision: number,
    private send: (revision: number, project: T) => Promise<{ revision: number }>,
    private notify: (status: SaveStatus) => void) { this.revision = revision; }

  update(project: T) {
    this.latest = structuredClone(project);
    this.sequence++;
    this.notify({ kind: 'saving', message: '正在保存…' });
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.timer = null; void this.flush().catch(() => {}); }, 200);
  }

  isDirty() { return this.sequence !== this.savedSequence; }

  async flush(): Promise<void> {
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    if (this.inflight) {
      await this.inflight;
      if (this.isDirty()) return this.flush();
      return;
    }
    if (!this.latest || !this.isDirty()) return;
    const sequence = this.sequence;
    const snapshot = structuredClone(this.latest);
    this.notify({ kind: 'saving', message: '正在保存…' });
    const commit = this.send(this.revision, snapshot).then(result => {
      this.revision = result.revision;
      this.savedSequence = sequence;
      if (!this.isDirty()) this.notify({ kind: 'saved', message: '已保存到本机' });
    }).catch((error: unknown) => {
      this.notify({ kind: 'error', message: error instanceof Error ? error.message : '保存失败，请重试' });
      throw error;
    });
    this.inflight = commit;
    try { await commit; } finally { this.inflight = null; }
    if (this.isDirty()) return this.flush();
  }

  dispose() { if (this.timer) clearTimeout(this.timer); }
}
