import math, gzip, base64

W, H = 1080, 2340
STRIDE = 4320          # 1080 pixels × 4 bytes, no padding
FBSZ = STRIDE * H     # 10,183,680 bytes

# Background row: visible pixels + zero padding to stride
vis = bytes([0x17, 0x11, 0x0d, 0xff] * W)
pad = bytes(STRIDE - W * 4)
buf = bytearray((vis + pad) * H)

def sp(x, y, B, G, R):
    if 0 <= x < W and 0 <= y < H:
        o = y * STRIDE + x * 4
        buf[o]=B; buf[o+1]=G; buf[o+2]=R; buf[o+3]=0xff

def ln(x0,y0,x1,y1,B,G,R):
    dx=abs(x1-x0); dy=abs(y1-y0)
    sx=1 if x0<x1 else -1; sy=1 if y0<y1 else -1
    e=dx-dy
    while True:
        sp(x0,y0,B,G,R)
        if x0==x1 and y0==y1: break
        e2=2*e
        if e2>-dy: e-=dy; x0+=sx
        if e2<dx: e+=dx; y0+=sy

print("Drawing hex grid...")
Z=70; HW=Z*math.sqrt(3)
for r in range(-1,int(H/(Z*1.5))+3):
    for c in range(-1,int(W/HW)+3):
        cx=int(c*HW+(r%2)*HW/2); cy=int(r*Z*1.5)
        p=[(int(cx+Z*math.cos(math.radians(60*i-30))),
            int(cy+Z*math.sin(math.radians(60*i-30)))) for i in range(6)]
        for i in range(6):
            ln(p[i][0],p[i][1],p[(i+1)%6][0],p[(i+1)%6][1],52,38,0)
        for a in range(-3,4):
            for b in range(-3,4):
                if a*a+b*b<=6:
                    sp(cx+b,cy+a,95,72,0)

F={'N':['#   #','##  #','# # #','#  ##','#   #'],
   'E':['#####','#    ','#### ','#    ','#####'],
   'R':['#### ','#   #','#### ','# #  ','#  ##'],
   'V':['#   #','#   #',' # # ',' # # ','  #  '],
   'O':[' ### ','#   #','#   #','#   #',' ### '],
   'S':[' ####','#    ',' ### ','    #','#### ']}

def dt(s,x0,y0,sc,B,G,R):
    cx=x0
    for ch in s:
        g=F.get(ch,[])
        if g:
            for ry,rw in enumerate(g):
                for rx,cv in enumerate(rw):
                    if cv=='#':
                        for dy in range(sc):
                            for dxx in range(sc):
                                sp(cx+rx*sc+dxx,y0+ry*sc+dy,B,G,R)
            cx+=(len(g[0])+1)*sc

print("Drawing text...")
SC=18
T='NERVEOS'
TW=sum((len(F[c][0])+1)*SC for c in T)-SC
TX=(W-TW)//2; TY=H//2-80
dt(T,TX,TY,SC,195,215,0)

print("Drawing circle...")
CX=W//2; CY=TY-90
for t in range(360):
    a=math.radians(t)
    for rr in range(60,68):
        sp(int(CX+rr*math.cos(a)),int(CY+rr*math.sin(a)),145,160,0)
for aa in range(-9,10):
    for bb in range(-9,10):
        if aa*aa+bb*bb<=81:
            sp(CX+bb,CY+aa,185,200,0)

raw = bytes(buf)
print(f"Raw: {len(raw)} bytes (stride={STRIDE})")
gz = gzip.compress(raw, compresslevel=9)
print(f"Gzipped: {len(gz)} bytes")
b64 = base64.b64encode(gz)
print(f"Base64: {len(b64)} chars, {(len(b64)+349)//350} chunks")

with open(r'C:\Windows\Temp\logo.gz', 'wb') as f: f.write(gz)
with open(r'C:\Windows\Temp\logo.gz.b64', 'wb') as f: f.write(b64)
print("Done.")
