export function exportName(input: string) {
  const invalid = '<>:"/\\|?*';
  let name = Array.from(input.trim()).map(char => char.charCodeAt(0)<32 || invalid.includes(char) ? '_' : char).join('');
  name = name.replace(/\.png$/i,'').replace(/[. ]+$/,'').slice(0,100) || '未命名封面';
  if (/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(name)) name += '_';
  return name+'.png';
}
