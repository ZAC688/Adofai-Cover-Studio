import { describe, it, expect, vi } from 'vitest';
import { SaveQueue, type SaveStatus } from './saveQueue';

describe('durable save scheduling', () => {
  it('does not claim saved when an older snapshot completes', async () => {
    let release: (value: {revision: number}) => void = () => {};
    const requests: {revision: number; name: string}[] = [];
    const statuses: SaveStatus[] = [];
    const queue = new SaveQueue<{name: string}>(0, (revision, project) => {
      requests.push({revision, name: project.name});
      return requests.length === 1 ? new Promise(resolve => {release = resolve;}) : Promise.resolve({revision: 2});
    }, status => statuses.push(status));
    queue.update({name: 'first'});
    const pending = queue.flush();
    queue.update({name: 'second'});
    release({revision: 1});
    await pending;
    expect(requests).toEqual([{revision: 0, name: 'first'}, {revision: 1, name: 'second'}]);
    expect(statuses.filter(s => s.kind === 'saved')).toHaveLength(1);
    expect(queue.isDirty()).toBe(false);
    queue.dispose();
  });

  it('retains failed snapshot and revision for explicit retry', async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error('disk full')).mockResolvedValueOnce({revision: 8});
    const queue = new SaveQueue(7, send, () => {});
    const original = {name: 'keep me'};
    queue.update(original); original.name = 'uncommitted mutation';
    await expect(queue.flush()).rejects.toThrow('disk full');
    expect(queue.isDirty()).toBe(true);
    expect(queue.revision).toBe(7);
    await queue.flush();
    expect(send).toHaveBeenLastCalledWith(7, {name: 'keep me'});
    expect(queue.isDirty()).toBe(false);
    queue.dispose();
  });
});
