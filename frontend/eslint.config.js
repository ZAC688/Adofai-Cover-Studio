import js from '@eslint/js';
import tseslint from 'typescript-eslint';
export default tseslint.config(js.configs.recommended, ...tseslint.configs.recommended,
  { ignores: ['dist'] },
  { files: ['**/*.ts', '**/*.tsx'], languageOptions: { globals: { document: 'readonly', window: 'readonly', console: 'readonly', Image: 'readonly', URL: 'readonly', fetch: 'readonly', requestAnimationFrame: 'readonly', ResizeObserver: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly', Blob: 'readonly', FileReader: 'readonly', File: 'readonly', HTMLCanvasElement: 'readonly', HTMLImageElement: 'readonly', PointerEvent: 'readonly', KeyboardEvent: 'readonly', Headers: 'readonly', DOMException: 'readonly', structuredClone: 'readonly' } } });
