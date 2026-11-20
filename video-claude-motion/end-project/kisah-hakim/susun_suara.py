"""Susun suara latar ikut babak + jana subs.js (sari kata karaoke) untuk scene.html.

Guna: python3 susun_suara.py <suara.mp3> <suara.whisper.json> <output_suara.wav>
"""
import sys, json, subprocess, re

SRC, WJ, OUT = sys.argv[1:4]
DUR = 74.0
# Klip tambahan: (fail, mula_src, tamat_src, mula_video)
EXTRA = [('suara-url-1.mp3', 0.0, 1.9, 71.0)]
# Blok suara: (mula_src, tamat_src, mula_video) — satu blok untuk setiap babak
BLOCKS = [(0.0, 3.1, 1.0), (3.45, 6.55, 6.0), (6.85, 10.35, 12.0), (10.75, 16.5, 18.6), (16.9, 21.7, 26.4),
          (22.4, 28.2, 32.4), (28.6, 33.2, 40.6), (33.6, 42.95, 48.3), (43.6, 48.9, 57.6), (49.35, 54.08, 63.6)]
HIDE_FROM = 49.35   # ayat penutup dipapar sebagai teks besar, bukan sari kata
FIX = {'24': '24', '5': 'Lima', 'Sehat': 'Sihat', 'Keritanya': 'Keretanya'}
HL = {'24', 'jam', 'Kecuali', 'Allah.', 'pertolongan', 'menolong', 'Sihat', 'masa', 'lapang.', 'sentiasa'}

def to_video(t):
    for a, b, v in BLOCKS:
        if a - .05 <= t <= b + .05:
            return round(v + (t - a), 3)
    return None

segs = json.load(open(WJ))
lines = []
for s in segs:
    ws, i = s['words'], 0
    out = []
    while i < len(ws):
        w = dict(ws[i]); txt = FIX.get(w['w'], w['w'])
        if txt == 'Dari' and i + 1 < len(ws) and ws[i + 1]['w'] == 'pada':
            txt = 'Daripada'; i += 1
        elif txt.startswith('-') and out:
            out[-1]['w'] += txt; i += 1; continue
        elif txt.lower().startswith('sallallahu'):
            j = i
            while j + 1 < len(ws) and not ws[j]['w'].lower().startswith('bersabda'): j += 1
            out.append({'w': '<span style="font-family:Amiri;font-style:normal">ﷺ</span>', 's': to_video(w['s']), 'hl': False}); i = j + 1; continue
        out.append({'w': txt, 's': to_video(w['s']), 'hl': txt in HL}); i += 1
    if not out or out[0]['s'] is None: continue
    lines.append({'s': out[0]['s'], 'e': to_video(s['e']) or out[-1]['s'] + .6, 'words': out, 'hide': s['s'] >= HIDE_FROM - .05})

open('subs.js', 'w').write('window.TIMEMAP=[[0,0],[%s,%s]];\nwindow.LINES=%s;\n' % (DUR, DUR, json.dumps(lines, ensure_ascii=False)))

# Trek suara
f, labels = '', ''
ALL = [(0, a, b, v) for a, b, v in BLOCKS] + [(i + 1, a, b, v) for i, (_, a, b, v) in enumerate(EXTRA)]
for k, (src, a, b, v) in enumerate(ALL):
    d = b - a; ms = int(v * 1000)
    f += f'[{src}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.03,afade=t=out:st={d - .1:.3f}:d=0.1,adelay={ms}|{ms}[a{k}];'
    labels += f'[a{k}]'
f += f'{labels}amix=inputs={len(ALL)}:normalize=0,apad=whole_dur={DUR},atrim=0:{DUR},loudnorm=I=-16:TP=-1.5:LRA=11'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', SRC] + sum([['-i', e[0]] for e in EXTRA], []) + ['-filter_complex', f, '-ar', '48000', '-ac', '2', OUT], check=True)
print('Siap:', len(lines), 'baris sari kata;', OUT)
