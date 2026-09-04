from pathlib import Path
import json

from PIL import Image, ImageDraw

from agentcut.editor import Editor
from agentcut.gen3 import tile_plan, stitch_tiles, chroma_key_image, write_remotion_bundle, extract_tiles
from agentcut.project import validate_project


def make_bg(path: Path, size=(640, 360)):
    im = Image.new('RGB', size, '#243044')
    d = ImageDraw.Draw(im)
    d.rectangle((0, int(size[1]*.62), size[0], size[1]), fill='#6c6254')
    d.line((0, int(size[1]*.78), size[0], int(size[1]*.63)), fill='#c9b48a', width=8)
    im.save(path)


def make_actor(path: Path):
    im = Image.new('RGB', (220, 360), '#FF00FF')
    d = ImageDraw.Draw(im)
    d.ellipse((70, 25, 150, 105), fill='#f0d1bb')
    d.rectangle((60, 105, 160, 310), fill='#445e4a')
    d.rectangle((75, 310, 105, 355), fill='#222222')
    d.rectangle((115, 310, 145, 355), fill='#222222')
    im.save(path)


def test_gen3_project_scene_card_actor_and_remotion_bundle(tmp_path: Path):
    root = tmp_path / 'p'
    e = Editor.create(root, width=1920, height=1080, fps=30, name='Gen3')
    e.configure_gen3(target_profile='uhd_4k30', actor_matte_key='#FF00FF')
    bg = tmp_path / 'bg.png'; make_bg(bg)
    bgrow = e.add_asset(str(bg), asset_id='bg')
    e.add_scene('bg', 7.0, scene_id='s1')
    e.set_gen3_scene('s1', kind='exhibit', category='科幻', work_title='Test', motion='static')
    e.set_gen3_card('s1', title='《测试作品》', subtitle='作者', body='这是两行以内的信息卡，用于验证第三代文学篇工作流。', start=2.2, duration=2.8, category='科幻')
    actor_src = tmp_path / 'actor.png'; make_actor(actor_src)
    actor = e.register_gen3_actor_card(str(actor_src), asset_id='chito')
    e.place_gen3_actor('s1', 'chito', x=.42, floor_y=.88, scale=.55, end_x=.46, shadow_asset_id=actor['shadow_asset_id'])
    compiled = e.compile_gen3(['s1'])
    assert compiled['compiled'] == 1
    p = e.get_project(); validate_project(p)
    assert p['gen3']['target_profile'] == 'uhd_4k30'
    assert p['scenes'][0]['gen3']['category'] == '科幻'
    ids = {x['id'] for x in p['scenes'][0]['layers']}
    assert 'gen3_category_text' in ids and 'gen3_card_blur' in ids
    assert any(x.startswith('gen3_actor_') for x in ids)
    rgba = Image.open(root / p['assets']['chito']['path']).convert('RGBA')
    assert rgba.getpixel((0,0))[3] < 10
    assert rgba.getpixel((110,180))[3] > 240
    out = write_remotion_bundle(p, root, tmp_path/'remotion')
    assert (out/'package.json').exists()
    manifest = json.loads((out/'public/manifest.json').read_text())
    assert manifest['schema'] == 'agentcut-gen3-remotion-v1'
    assert manifest['scenes'][0]['asset_path'].startswith('assets/')
    assert manifest['scenes'][0]['gen3']['actors'][0]['asset_path'].startswith('assets/')


def test_gen3_tile_plan_and_stitch(tmp_path: Path):
    plan = tile_plan(1000, 600, rows=2, cols=2, overlap=.12)
    assert len(plan['tiles']) == 4
    tiles=[]
    for i in range(4):
        p=tmp_path/f't{i}.png'; Image.new('RGB',(320,200),(40+i*20,50,70)).save(p); tiles.append(p)
    out=stitch_tiles(tiles,tmp_path/'stitched.png',rows=2,cols=2,overlap=.12)
    im=Image.open(out)
    assert im.width > 320 and im.height > 200


def test_chroma_ignores_bad_source_alpha(tmp_path: Path):
    src=tmp_path/'bad.png'
    im=Image.new('RGBA',(20,20),(255,0,255,80))
    d=ImageDraw.Draw(im); d.rectangle((5,5,14,14), fill=(255,255,255,80)); im.save(src)
    out=chroma_key_image(src,tmp_path/'out.png')
    r=Image.open(out).convert('RGBA')
    assert r.getpixel((0,0))[3] < 10
    assert r.getpixel((10,10))[3] > 240


def test_extract_tiles_manifest(tmp_path: Path):
    src=tmp_path/'master.png'; Image.new('RGB',(1000,600),'#334455').save(src)
    m=extract_tiles(src,tmp_path/'tiles',rows=2,cols=2,overlap=.12)
    assert len(m['tiles']) == 4
    sizes=[Image.open(tmp_path/'tiles'/t['path']).size for t in m['tiles']]
    assert len(set(sizes)) == 1
    assert (tmp_path/'tiles'/'tile_manifest.json').exists()
