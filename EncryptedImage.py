import sys
import math
import random
from PIL import Image
import colorsys
import operator
from optparse import OptionParser

options = OptionParser(usage='%prog [options] file',
                       description='Colorize data file according '
                                   'to repetitive chunks, typical in ECB encrypted data')
options.add_option('-c', '--colors', type='int', default=16,
                  help='Number of colors to use, default=16')
options.add_option('-P', '--palette',
                  help='Provide list of colors as hex or RGB palette')
options.add_option('-b', '--blocksize', type='int', default=16,
                  help='Blocksize in bytes, default=16')
options.add_option('-g', '--groups', type='int', default=1,
                  help='Groups of N blocks, default=1')
options.add_option('-r', '--ratio', help='Output image ratio, e.g. -r 4:3')
options.add_option('-x', '--width', type='float', help='Width of output image')
options.add_option('-y', '--height', type='int', help='Height of output image')
options.add_option('-s', '--sampling', type='int', default=1000,
                  help='Sampling when guessing image size, default=1000')
options.add_option('-m', '--maxratio', type='int', default=3,
                  help='Max ratio to test when guessing image size, default=3')
options.add_option('-o', '--offset', type='float', default=0,
                  help='Offset to skip original header in number of blocks')
options.add_option('-f', '--flip', action="store_true", default=False,
                  help='Flip image top<>bottom')
options.add_option('-p', '--pixelwidth', type='int', default=1,
                  help='Bytes per pixel in original image')
options.add_option('-R', '--raw', action="store_true", default=False,
                  help='Display raw image in 256 colors')
options.add_option('-S', '--save', action="store_true", default=False,
                  help='Save a copy of the produced image')
options.add_option('-O', '--output', help='Change default output location prefix, e.g. -O /tmp/mytest. Implies -S')
options.add_option('-D', '--dontshow', action="store_true", default=False,
                  help='Don\'t display image')

def histogram(data, blocksize):
    d = {}
    for k in range(len(data) // blocksize):
        block = data[k * blocksize:(k + 1) * blocksize].hex()
        d[block] = d.get(block, 0) + 1
    return sorted(d.items(), key=operator.itemgetter(1), reverse=True)

opts, args = options.parse_args()
if len(args) < 1:
    options.print_help()
    sys.exit()

if opts.colors < 2:
    print("Please choose at least two colors")
    sys.exit()

if opts.width is not None and opts.height is not None:
    print("Please indicate only -x or -y, not both!")
    sys.exit()

if opts.ratio is not None and (opts.width is not None or opts.height is not None):
    print("Please don't mix -r with -x or -y!")
    sys.exit()

if opts.raw and (opts.colors != 16 or opts.blocksize != 16 or opts.groups != 1 or opts.palette):
    print("Please don't mix -R with -b, -c, -C or -g!")
    sys.exit()

if opts.output:
    opts.save = True

with open(args[0], 'rb') as f:
    f.read(int(round(opts.offset * opts.blocksize)))
    ciphertext = f.read()

if opts.raw:
    N = 256
    HSV_tuples = [(x / N, 0.8, 0.8) for x in range(N)]
    RGB_tuples = [colorsys.hsv_to_rgb(*x) for x in HSV_tuples]
    p = [int(pp * 255) for rgb in RGB_tuples for pp in rgb]
    out = ciphertext[::opts.pixelwidth]
else:
    histo = histogram(ciphertext, opts.blocksize)
    histo = [x for x in histo if x[1] > 1][: (opts.colors - 1) * opts.groups]
    histo = histo[:len(histo) // opts.groups * opts.groups]
    if not histo:
        raise ValueError("Did not find any single match :-(")

    N = 254
    HSV_tuples = [(x / N, 0.8, 0.8) for x in range(N)]
    RGB_tuples = [colorsys.hsv_to_rgb(*x) for x in HSV_tuples]
    p = [1, 1, 1] + [int(pp * 255) for rgb in RGB_tuples for pp in rgb] + [0, 0, 0]

    bcolormap = {}
    for i, (token, count) in enumerate(histo):
        color = int(opts.palette[i * 2:i * 2 + 2], 16) if opts.palette and i > 0 else 0
        bcolormap[token] = bytes([color])
        print(f"{token} {count:10} #{color:02X} -> #{p[color * 3]:02X} #{p[(color * 3) + 1]:02X} #{p[(color * 3) + 2]:02X}")

    blocksleft = len(ciphertext) // opts.blocksize - sum(n for _, n in histo)
    color = int(opts.palette[-2:], 16) if opts.palette else 255
    print(f"{'*' * len(histo[0][0])} {blocksleft:10} #{color:02X} -> #{p[color * 3]:02X} #{p[(color * 3) + 1]:02X} #{p[(color * 3) + 2]:02X}")
    
    bcolor = bytes([color])
    out = bytearray((len(ciphertext) // opts.pixelwidth) + 1)
    outi = 0

    for i in range(len(ciphertext) // opts.blocksize):
        token = ciphertext[i * opts.blocksize:(i + 1) * opts.blocksize].hex()
        byte = bcolormap.get(token, bcolor)
        b = opts.blocksize // opts.pixelwidth
        out[outi:outi + b] = byte * b
        outi += b

if opts.width is None and opts.height is None and opts.ratio is None:
    print(f"Trying to guess ratio between 1:{opts.maxratio} and {opts.maxratio}:1 ...")
    sq = int(math.sqrt(len(out)))
    r = {i: sum(x == y for x, y in zip(out[:-i:opts.sampling], out[i::opts.sampling])) / (len(out[:-i:opts.sampling])) for i in range(sq // opts.maxratio, sq * opts.maxratio)}
    opts.width = max(r.items(), key=operator.itemgetter(1))[0]

if opts.ratio is not None:
    ratio = tuple(map(int, opts.ratio.split(':')))
    l = len(out)
    x = math.sqrt(float(ratio[0]) / ratio[1] * l)
    y = x / ratio[0] * ratio[1]
    xy = (int(x), int(y))

if opts.width is not None:
    if int(opts.width) != opts.width:
        out = bytearray(out[i * int(opts.width):(i + 1) * int(opts.width)] for i in range(len(out) // int(opts.width)))

if opts.height is not None:
    xy = (len(out) // opts.height, opts.height)

print("Size:", repr(xy))

i = Image.frombytes('P', xy, bytes(out))
i.putpalette(p)

if opts.flip:
    i = i.transpose(Image.FLIP_TOP_BOTTOM)

if opts.save:
    suffix = ".raw_p%i" % opts.pixelwidth if opts.raw else ".b%i_p%i_c%i" % (opts.blocksize, opts.pixelwidth, opts.colors)
    if opts.groups != 1:
        suffix += "_g%i" % opts.groups
    if opts.offset != 0:
        suffix += "_o%s" % repr(opts.offset)
    if opts.width is not None:
        suffix += "_x%s_y%i" % (repr(opts.width), xy[1])
    else:
        suffix += "_x%i_y%i" % xy
    print(f"Saving output into {opts.output}{suffix}.png")
    i.save(f"{opts.output}{suffix}.png")

if not opts.dontshow:
    i.show()

