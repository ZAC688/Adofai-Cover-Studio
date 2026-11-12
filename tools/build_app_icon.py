"""Render the existing code-native header logo into portable Windows icons."""
import io
from pathlib import Path
import re

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def logo_html():
    css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
    rule=re.search(r'\.brand-mark\{[^}]+\}',css).group()
    return '<style>html,body{margin:0;background:transparent;font-family:"Segoe UI","Microsoft YaHei",sans-serif}*{box-sizing:border-box}'+rule+'</style><span class="brand-mark">A</span>'


def build():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(device_scale_factor=8)
        page.set_content(logo_html())
        raw=page.locator('.brand-mark').screenshot(omit_background=True)
        browser.close()
    image=Image.open(io.BytesIO(raw)).convert('RGBA').resize((256,256),Image.Resampling.LANCZOS)
    output=ROOT/'frontend/public'
    image.save(output/'app-icon.png')
    image.save(output/'app-icon.ico',format='ICO',sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
    print('Rendered the existing header logo as 256px PNG and seven-size Windows ICO.')


if __name__=='__main__':build()
