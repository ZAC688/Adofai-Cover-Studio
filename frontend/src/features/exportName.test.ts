import { expect, it } from 'vitest';
import { exportName } from './exportName';
it('produces usable Windows PNG filenames', () => {
  expect(exportName('my:cover?')).toBe('my_cover_.png');
  expect(exportName('CON')).toBe('CON_.png');
  expect(exportName('   ')).toBe('未命名封面.png');
  expect(exportName('曲名.PNG')).toBe('曲名.png');
});
