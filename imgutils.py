from config import *

asciis = '@W- '

if SHOW_USER_IMG:
    from PIL import Image

def image_to_ascii(imgpath):
    img = Image.open(imgpath)
    img = img.convert('L')
    img = img.resize((20, 10))

    w, h = img.size
    gli = []
    gln = []

    for y in range(h):
        for x in range(w):
            px = img.getpixel((x, y))
            gln.append(asciis[int((px / 255) * (len(asciis)-1))])
        gli.append(gln.copy())
        gln = []
    return gli

for ln in image_to_ascii('nz.jpg'):
    for px in ln:
        print(px, end='')
    print()