import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import pytest

from backend.app.chart_style import reference_polygon, stone_texture, reference_icon
from experiments.static_track_probe import Tile, build_track
from experiments.static_track_editor import browser_chart
from experiments.static_track_export import render_selection, selection_scene


def test_right_angle_has_square_outer_corner_and_recessed_inner_join():
    polygon=reference_polygon(Tile(0,0,0,180,90))
    assert (.29,-.29) in polygon
    assert (-.29,.29) in polygon
    assert (-.5,-.29) in polygon and (.29,.5) in polygon
    assert len(polygon)==6


@pytest.mark.parametrize('angle',range(0,360,15))
def test_ports_rotate_without_drifting_or_inventing_track_connections(angle):
    tile=Tile(0,10,-5,(angle+180)%360,(angle+90)%360)
    points=reference_polygon(tile)
    base=reference_polygon(Tile(0,0,0,180,90))
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    np.testing.assert_allclose(points,[(10+x*c-y*s,-5+x*s+y*c) for x,y in base],atol=1e-12)


def test_shared_scene_browser_and_svg_have_identical_reference_geometry_and_relief(tmp_path):
    track=build_track({'pathData':'RRUULLDD','settings':{'trackColor':'336699'}})
    scene=selection_scene(track,reference=True,style='gold')
    browser=browser_chart(track,'demo','demo',(0,8),reference=True)
    for native,web in zip(scene['tiles'],browser['tiles']):
        np.testing.assert_allclose(native['polygon'],web['polygon'],atol=1e-6)
        assert len(native['surface'])==len(web['surface'])>0
    target=tmp_path/'track.png'
    render_selection(track,target,width=960,height=600,padding=35,reference=True,style='gold')
    svg=ET.parse(target.with_suffix('.svg')).getroot()
    assert len(svg.findall('.//{*}polyline[@data-detail="bevel"]'))==sum(len(t['surface']) for t in scene['tiles'])
    data=np.asarray(Image.open(target))
    assert data[:,:,3].min()==0 and data[:,:,3].max()==255
    assert np.any(np.all(data[:,:,:3]==[242,216,152],axis=2))
    assert np.any(np.all(data[:,:,:3]==[161,138,86],axis=2))


def test_stone_is_opaque_reproducible_and_has_pits_instead_of_only_white_noise():
    data=np.asarray(stone_texture())
    assert data.shape==(512,512,4) and np.all(data[:,:,3]==255)
    assert np.mean(data[:,:,0]<180)>.01
    assert not np.array_equal(data[:128,:128],data[:128,128:256])
    np.testing.assert_array_equal(data,np.asarray(stone_texture()))


def test_spiral_core_outline_and_directional_arrow_remain_separate():
    a,b=reference_icon('twirl',True),reference_icon('twirl',False)
    assert [p['stroke'] for p in a[:3]]==['#704051ff','#efacc7ff','#8552a9ff']
    assert a[-1]['stroke']=='#4477d5ff' and b[-1]['stroke']=='#df493cff'
    assert len(a[0]['points'])>90 and len(a[-1]['points'])==3
    assert reference_icon('rabbit')[0]['kind']=='polygon'
    assert len(reference_icon('rabbit')[0]['points'])>100


def test_gold_palette_matches_unlit_official_reference_body():
    root=Path(__file__).resolve().parents[2]
    source=root/'testscreenshots/test_2/Screenshot 2026-11-06 125645.png'
    data=np.asarray(Image.open(source).convert('RGB'))
    r,g,b=[data[:,:,i].astype(int) for i in range(3)]
    body=data[(r>150)&(r<245)&(g>125)&(g<220)&(b>75)&(b<165)&(r-g>12)&(g-b>25)]
    assert len(body)>5000
    actual=np.median(np.asarray(stone_texture())[:,:,:3],axis=(0,1))
    reference=np.median(body,axis=0)
    assert np.max(np.abs(actual-reference))<=15,(actual,reference)
