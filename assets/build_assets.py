#!/usr/bin/env python3
"""Render the editable vector mark and original LiveArea art with Pillow.

No downloaded imagery or third-party brand marks. Output is 8-bit indexed RGB
PNG without transparency, in the Vita system's required dimensions. Run from
any directory. Pillow and a system DejaVu Sans font are used only at asset-build
time; the Vita does not need an image decoder or a font dependency for these.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'sce_sys'
SCALE=3

def font(size,bold=False):
    return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',size*SCALE)

def canvas(w,h):return Image.new('RGB',(w*SCALE,h*SCALE),'black')

def label(image,position,text,size,color='#bdcbc3',bold=False,anchor=None):
    ImageDraw.Draw(image).text(tuple(int(p*SCALE) for p in position),text,font=font(size,bold),fill=color,anchor=anchor)

def mark(image,x,y,size):
    # Read the checked-in vector, so the icon and all LiveArea assets share it.
    vector=ET.parse(ROOT/'assets/mark.svg').getroot();draw=ImageDraw.Draw(image)
    factor=size*SCALE/128
    def box(a,b,c,d):return ((x*SCALE+a*factor),(y*SCALE+b*factor),(x*SCALE+c*factor),(y*SCALE+d*factor))
    for node in vector:
        tag=node.tag.rsplit('}',1)[-1];a=node.attrib
        if tag=='circle':
            cx,cy,r=(float(a[k]) for k in ('cx','cy','r'))
            draw.ellipse(box(cx-r,cy-r,cx+r,cy+r),fill=a['fill'],outline=a['stroke'],width=max(1,round(float(a['stroke-width'])*factor)))
        elif tag=='rect':
            xx,yy=float(a.get('x',0)),float(a.get('y',0));w,h=float(a['width']),float(a['height'])
            draw.rounded_rectangle(box(xx,yy,xx+w,yy+h),radius=round(float(a.get('rx',0))*factor),fill=a['fill'])

def save(image,path,size):
    path.parent.mkdir(parents=True,exist_ok=True)
    image=image.resize(size,Image.Resampling.LANCZOS)
    image=image.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    image.save(path,format='PNG',bits=8,optimize=True)
    assert image.mode=='P' and image.size==size

def main():
    icon=canvas(128,128);mark(icon,0,0,128)
    save(icon,DEST/'icon0.png',(128,128))
    background=canvas(840,500)
    mark(background,45,40,72)
    label(background,(137,51),'Vita Audio Receiver',25,bold=True)
    label(background,(138,91),'A quiet screen. Your music, everywhere at home.',14,'#668875')
    draw=ImageDraw.Draw(background)
    draw.line((48*SCALE,145*SCALE,792*SCALE,145*SCALE),fill='#193025',width=SCALE)
    label(background,(48,433),'PC AUDIO  /  SPOTIFY CONTROLS',14,'#64b38a')
    label(background,(48,461),'True black OLED mode   ·   Screen-off listening',13,'#668875')
    save(background,DEST/'livearea/contents/bg.png',(840,500))
    startup=canvas(280,158);mark(startup,96,0,88)
    label(startup,(140,91),'VITA AUDIO',19,bold=True,anchor='mt')
    label(startup,(140,119),'RECEIVER',13,'#74a98c',anchor='mt')
    save(startup,DEST/'livearea/contents/startup.png',(280,158))
    splash=canvas(960,544);mark(splash,416,151,128)
    label(splash,(480,306),'Vita Audio Receiver',24,bold=True,anchor='mt')
    label(splash,(480,350),'Connecting your music.',14,'#668875',anchor='mt')
    save(splash,DEST/'pic0.png',(960,544))
    print('Created indexed icon, LiveArea background/gate and launch image.')

if __name__=='__main__':main()
