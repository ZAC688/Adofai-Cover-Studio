import ctypes
import json
from ctypes import wintypes as w
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright,expect

from tests.icon_checks import ico_images
from .test_desktop_runtime import start_desktop,stop_desktop

ROOT=Path(__file__).resolve().parents[2]


def native_icon_pixels(handle):
    class IconInfo(ctypes.Structure):
        _fields_=[('icon',w.BOOL),('x',w.DWORD),('y',w.DWORD),('mask',w.HBITMAP),('color',w.HBITMAP)]
    class Bitmap(ctypes.Structure):
        _fields_=[('type',w.LONG),('width',w.LONG),('height',w.LONG),('stride',w.LONG),('planes',w.WORD),('bits',w.WORD),('data',ctypes.c_void_p)]
    class Header(ctypes.Structure):
        _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('imageSize',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
    user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
    user.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];user.SendMessageW.restype=ctypes.c_void_p
    user.GetIconInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(IconInfo)]
    gdi.GetObjectW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
    gdi.DeleteObject.argtypes=[ctypes.c_void_p]
    user.GetDC.argtypes=[w.HWND];user.GetDC.restype=ctypes.c_void_p
    user.ReleaseDC.argtypes=[w.HWND,ctypes.c_void_p]
    gdi.GetDIBits.argtypes=[ctypes.c_void_p,ctypes.c_void_p,w.UINT,w.UINT,ctypes.c_void_p,ctypes.c_void_p,w.UINT]
    icon=user.SendMessageW(handle,0x007f,1,0)
    assert icon,'Main window has no large application icon'
    info=IconInfo();assert user.GetIconInfo(icon,ctypes.byref(info))
    dc=user.GetDC(None)
    try:
        bitmap=Bitmap();assert gdi.GetObjectW(info.color,ctypes.sizeof(bitmap),ctypes.byref(bitmap))
        header=Header();header.size=ctypes.sizeof(header);header.width=bitmap.width;header.height=-bitmap.height;header.planes=1;header.bits=32
        pixels=(ctypes.c_ubyte*(bitmap.width*bitmap.height*4))()
        assert gdi.GetDIBits(dc,info.color,0,bitmap.height,pixels,ctypes.byref(header),0)==bitmap.height
        return np.ctypeslib.as_array(pixels).reshape(bitmap.height,bitmap.width,4)[:,:,[2,1,0,3]].copy()
    finally:
        user.ReleaseDC(None,dc);gdi.DeleteObject(info.color);gdi.DeleteObject(info.mask)


def test_logo_png_and_ico_have_all_sizes_transparency_and_monochrome_artwork():
    png=ROOT/'frontend/public/app-icon.png';ico=ROOT/'frontend/public/app-icon.ico'
    assert {size for size,_ in ico_images(ico)}=={(n,n) for n in (16,24,32,48,64,128,256)}
    data=np.asarray(Image.open(png))
    assert data.shape==(256,256,4) and data[0,0,3]==0
    assert np.all(data[:,:,:3][:,:,0]==data[:,:,:3][:,:,1])
    assert np.sum((data[:,:,0]<40)&(data[:,:,3]==255))>1000
    assert np.sum((data[:,:,0]>230)&(data[:,:,3]==255))>10000


def assert_desktop_logo(tmp_path,binary=None):
    host=start_desktop(tmp_path,binary=binary)
    try:
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True,timeout=15000)
            page=browser.contexts[0].pages[0]
            expect(page.locator('.topbar .brand-mark')).to_have_text('A',timeout=30000)
            expect(page.locator('link[rel="icon"]')).to_have_attribute('href','/app-icon.png')
            state=host['client'].get(host['url']+'/api/health');assert state.status_code==200
            handle=json.loads(host['ready'].read_text(encoding='utf-8'))['windowHandle']
            native=native_icon_pixels(handle);size=native.shape[0]
            expected=np.asarray(Image.open(ROOT/'frontend/public/app-icon.ico').ico.getimage((size,size)))
            assert native.shape==expected.shape
            opaque=expected[:,:,3]==255
            np.testing.assert_allclose(native[:,:,:3][opaque],expected[:,:,:3][opaque],atol=1)
            assert host['client'].get(host['url']+'/app-icon.png').content==(ROOT/'frontend/public/app-icon.png').read_bytes()
    finally:stop_desktop(host)


def test_real_native_window_uses_header_logo(tmp_path):assert_desktop_logo(tmp_path)
