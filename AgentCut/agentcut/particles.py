from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .errors import AgentCutError
from .libraries import material_defaults
from .util import ensure_binary, hash_obj

DIRECTION_VECTORS = {
    "up": (0.0, -1.0), "down": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "up_left": (-math.sqrt(0.5), -math.sqrt(0.5)), "up_right": (math.sqrt(0.5), -math.sqrt(0.5)),
    "down_left": (-math.sqrt(0.5), math.sqrt(0.5)), "down_right": (math.sqrt(0.5), math.sqrt(0.5)),
}
DEPTH_FACTORS = {
    "background": {"size": 0.55, "speed": 0.65, "count": 0.75},
    "midground": {"size": 0.78, "speed": 0.82, "count": 0.9},
    "foreground": {"size": 1.0, "speed": 1.0, "count": 1.0},
}
PROXY_SCALE = {
    "snow": 0.55, "rain": 0.55, "dust": 0.45, "fog": 0.40, "smoke": 0.40,
    "embers": 0.50, "sparks": 0.50, "fire": 0.45, "ash": 0.45,
    "bokeh": 0.40, "light_particles": 0.50,
}


def _rgb(hex_color: str, fallback=(255,255,255)) -> tuple[int,int,int]:
    try:
        h=hex_color.lstrip('#')
        if len(h)==6:
            return tuple(int(h[i:i+2],16) for i in (0,2,4))
    except Exception:
        pass
    return fallback


def particle_proxy_scale(effect: dict) -> float:
    return float(effect.get("render_scale", PROXY_SCALE.get(effect.get("type", "snow"), 0.5)))


def particle_cache_path(cache_dir: Path, effect: dict, width: int, height: int, fps: int, duration: float) -> Path:
    scale = particle_proxy_scale(effect)
    key = hash_obj({"effect": effect, "width": width, "height": height, "fps": fps, "duration": round(duration,4), "proxy":scale})[:20]
    return cache_dir / f"particle_{key}.mp4"


def _direct(base_vx: float, base_vy: float, direction: str) -> tuple[float,float]:
    if direction == "auto": return base_vx, base_vy
    vec = DIRECTION_VECTORS.get(direction)
    if vec is None: return base_vx, base_vy
    magnitude=max(1.0,math.hypot(base_vx,base_vy))
    return vec[0]*magnitude, vec[1]*magnitude


def _wrap(value: float, extent: float, margin: float=0.0) -> float:
    span=extent+2*margin
    return (value+margin)%span-margin


def generate_particle_video(path: Path, effect: dict, width: int, height: int, fps: int, duration: float) -> Path:
    if path.exists() and path.stat().st_size>0: return path
    path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_name(f".{path.stem}.partial{path.suffix}")
    partial.unlink(missing_ok=True)
    scale=max(0.25,min(1.0,particle_proxy_scale(effect)))
    width=max(64,int(width*scale)//2*2); height=max(64,int(height*scale)//2*2)
    ffmpeg=ensure_binary("ffmpeg")
    frames=max(1,int(math.ceil(duration*fps)))
    effect_type=effect.get("type","snow")
    intensity=float(effect.get("intensity",0.2)); speed=max(0.05,float(effect.get("speed",1.0)))
    direction=effect.get("direction","auto"); depth=effect.get("depth","foreground")
    depth_f=DEPTH_FACTORS.get(depth,DEPTH_FACTORS["foreground"]); speed*=depth_f["speed"]
    seed=int(effect.get("seed",1)); rng=np.random.default_rng(seed)
    mat=material_defaults(effect.get("material")); base_color=_rgb(str(mat.get("color","#ffffff")))
    mat_size=float(mat.get("size",1.0)); softness=float(mat.get("softness",0.2))

    count_base={"snow":150,"rain":120,"dust":85,"fog":7,"smoke":9,"embers":65,"sparks":85,"fire":55,"ash":80,"bokeh":28,"light_particles":65}.get(effect_type,80)
    min_count=2 if effect_type in {"fog","smoke"} else 1
    count=max(min_count,int(count_base*(0.18+intensity*1.7)*depth_f["count"]))
    xs=rng.uniform(0,width,count); ys=rng.uniform(0,height,count)
    sizes=rng.uniform(1.0,4.0,count)*depth_f["size"]*mat_size*scale
    phase=rng.uniform(0,math.tau,count)

    proc=subprocess.Popen([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{width}x{height}","-r",str(fps),"-i","-","-an","-c:v","libx264","-preset","ultrafast","-crf","25","-pix_fmt","yuv420p",str(partial)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for frame_idx in range(frames):
            t=frame_idx/fps
            img=Image.new("RGB",(width,height),(0,0,0)); draw=ImageDraw.Draw(img)
            if effect_type=="snow":
                vx,vy=_direct(8*speed*scale,28*speed*scale,direction); sway=16*speed*scale
                for i in range(count):
                    y=_wrap(ys[i]+vy*t*(0.5+sizes[i]/max(2,4*scale)),height,12); x=_wrap(xs[i]+vx*t+math.sin(t*1.2+phase[i])*sway,width,12)
                    r=max(.7,sizes[i]*(0.7+intensity)); val=tuple(min(255,int(c*(0.74+0.26*intensity))) for c in base_color)
                    draw.ellipse((x-r,y-r,x+r,y+r),fill=val)
            elif effect_type=="rain":
                vx,vy=_direct(-40*speed*scale,500*speed*scale,direction); length=(13+24*intensity)*scale; norm=max(1,math.hypot(vx,vy)); lx,ly=vx/norm*length,vy/norm*length
                for i in range(count):
                    y=_wrap(ys[i]+vy*t*(0.7+sizes[i]/max(2,5*scale)),height,35); x=_wrap(xs[i]+vx*t,width,35)
                    draw.line((x,y,x+lx,y+ly),fill=base_color,width=max(1,int(sizes[i]/2)))
            elif effect_type in {"dust","light_particles","ash"}:
                base_vy={"dust":2.5,"light_particles":-7.0,"ash":7.0}[effect_type]
                vx,vy=_direct(2*speed*scale,base_vy*speed*scale,direction)
                for i in range(count):
                    y=_wrap(ys[i]+vy*t+math.cos(t*.7+phase[i])*7*scale,height); x=_wrap(xs[i]+vx*t+math.sin(t*.6+phase[i])*9*scale,width)
                    r=max(.6,sizes[i]*(.5+intensity)); draw.ellipse((x-r,y-r,x+r,y+r),fill=base_color)
            elif effect_type in {"embers","sparks"}:
                vy0=-58 if effect_type=="embers" else -85; vx0=3 if effect_type=="embers" else 12
                vx,vy=_direct(vx0*speed*scale,vy0*speed*scale,direction)
                for i in range(count):
                    y=_wrap(ys[i]+vy*t*(.6+sizes[i]/max(2,5*scale)),height,20); x=_wrap(xs[i]+vx*t+math.sin(t*1.7+phase[i])*12*scale,width,20)
                    r=max(.7,sizes[i]*(.55+intensity)); draw.ellipse((x-r,y-r,x+r,y+r),fill=base_color)
            elif effect_type in {"fog","smoke"}:
                vx0=18 if effect_type=="fog" else 9; vy0=0 if effect_type=="fog" else -10
                vx,vy=_direct(vx0*speed*scale,vy0*speed*scale,direction); bands=max(2,count)
                for i in range(bands):
                    cx=_wrap(xs[i]+vx*t,width,width*.25); cy=_wrap(ys[i]+vy*t,height,height*.12)
                    rw=width*(.16+.15*((i%3)/2))*depth_f["size"]; rh=height*(.035+.04*((i%4)/3))*depth_f["size"]
                    factor=.55+.35*intensity if effect_type=="smoke" else .75+.2*intensity
                    color=tuple(int(c*factor) for c in base_color); draw.ellipse((cx-rw,cy-rh,cx+rw,cy+rh),fill=color)
                img=img.filter(ImageFilter.GaussianBlur(radius=max(5,int((14+22*intensity)*scale))))
            elif effect_type=="fire":
                # Stylized deterministic flame bed. Outer orange tongues + yellow inner cores
                # are concentrated at the lower edge so the result reads as flame, not sparks.
                glow=Image.new("RGB",(width,height),(0,0,0)); gd=ImageDraw.Draw(glow)
                band_h=max(8,int(height*(0.08+0.08*intensity)))
                gd.rectangle((0,height-band_h,width,height),fill=(120,24,2))
                glow=glow.filter(ImageFilter.GaussianBlur(radius=max(6,int(18*scale))))
                img=Image.blend(img,glow,min(0.55,0.18+0.35*intensity)); draw=ImageDraw.Draw(img)
                flame_count=max(18,int(count*.75))
                for i in range(flame_count):
                    lane=(i+.5)/flame_count
                    x=(lane*width + math.sin(t*2.6+phase[i])*26*scale) % width
                    pulse=0.72+0.28*math.sin(t*(3.5+0.25*(i%4))+phase[i])
                    height_i=(height*(0.07+0.16*intensity)*(0.55+0.7*((i%7)/6))*pulse)
                    base_y=height*(0.99-0.015*((i%3)/2))
                    half=max(3.0,sizes[i]*(2.4+2.8*intensity))
                    # Tapered outer flame tongue.
                    pts=[(x-half,base_y),(x-half*.55,base_y-height_i*.35),(x,base_y-height_i),(x+half*.55,base_y-height_i*.35),(x+half,base_y)]
                    outer=(255,74+int(70*intensity),10) if i%3 else (255,105,18)
                    draw.polygon(pts,fill=outer)
                    if i%2==0:
                        inner_h=height_i*.58; inner_w=half*.44
                        pts2=[(x-inner_w,base_y),(x-inner_w*.35,base_y-inner_h*.35),(x,base_y-inner_h),(x+inner_w*.35,base_y-inner_h*.35),(x+inner_w,base_y)]
                        draw.polygon(pts2,fill=(255,210,72))
                img=img.filter(ImageFilter.GaussianBlur(radius=max(1,int((1.2+2.8*softness)*scale))))
            elif effect_type=="bokeh":
                vx,vy=_direct(3*speed*scale,-2*speed*scale,direction)
                for i in range(count):
                    x=_wrap(xs[i]+vx*t+math.sin(t*.3+phase[i])*6*scale,width,30); y=_wrap(ys[i]+vy*t,height,30)
                    r=max(4,sizes[i]*(4.5+5*intensity)); color=tuple(int(c*(.55+.4*((i%5)/4))) for c in base_color)
                    draw.ellipse((x-r,y-r,x+r,y+r),fill=color)
                img=img.filter(ImageFilter.GaussianBlur(radius=max(2,int((3+8*softness)*scale))))
            if proc.stdin is None: raise AgentCutError("PARTICLE_PIPE_FAILED","Particle encoder stdin unavailable")
            proc.stdin.write(np.asarray(img,dtype=np.uint8).tobytes())
        if proc.stdin: proc.stdin.close()
        stderr=proc.stderr.read().decode(errors="replace") if proc.stderr else ""; code=proc.wait()
        if code!=0: raise AgentCutError("PARTICLE_RENDER_FAILED","Failed to encode particle video",returncode=code,stderr=stderr[-4000:])
        if not partial.exists() or partial.stat().st_size<=0: raise AgentCutError("PARTICLE_RENDER_FAILED","Particle encoder produced empty file",path=str(partial))
        os.replace(partial,path)
    except Exception:
        proc.kill(); partial.unlink(missing_ok=True); raise
    return path
