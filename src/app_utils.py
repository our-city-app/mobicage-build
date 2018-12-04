# -*- coding: utf-8 -*-
# Copyright 2018 Mobicage NV
# NOTICE: THIS FILE HAS BEEN MODIFIED BY MOBICAGE NV IN ACCORDANCE WITH THE APACHE LICENSE VERSION 2.0
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.5@@

import itertools
import os
import re
import shutil
import subprocess
import warnings
from contextlib import contextmanager
from zipfile import ZipFile

from PIL import Image

import png

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

CURRENT_DIR = os.path.realpath(os.path.dirname(__file__))
ICON_LIBRARY_PATH = os.path.realpath(os.path.join(CURRENT_DIR, '..', 'res', 'icons.zip'))


def _create_dir_if_not_exists(path):
    path = os.path.dirname(path)
    if not os.path.exists(path):
        os.makedirs(path)


@contextmanager
def pushd(new_dir):
    prev_dir = os.getcwd()
    os.chdir(new_dir)
    yield
    os.chdir(prev_dir)


def get_icon_from_library(name, size=512):
    zipf = ZipFile(ICON_LIBRARY_PATH)
    try:
        return zipf.read("%s/%s.png" % (size, name))
    finally:
        zipf.close()


def download_icon(icon_key, icon_color, icon_size, file_path):
    if icon_color:
        icon_color = str(icon_color).replace("#", "")
    else:
        icon_color = "000000"

    print "Rendering icon: %s\tcolor=%s size=%s" % (icon_key, icon_color, icon_size)

    png_bytes = recolor_png(get_icon_from_library(icon_key, icon_size or 50), (0, 0, 0), parse_color(icon_color))
    _create_dir_if_not_exists(file_path)
    with open(file_path, 'wb+') as output:
        output.write(png_bytes)


def create_trusstore(app_id, file_path):
    subprocess.check_output('cd %s; rm -f truststore.bks' % CURRENT_DIR, shell=True)
    command = 'cd %s; CLASSPATH=bcprov-jdk15on-146.jar keytool -noprompt -import -alias "ca cert" ' \
              '-file %s/ca.cert.pem -keystore truststore.bks -storetype BKS -provider ' \
              'org.bouncycastle.jce.provider.BouncyCastleProvider -providerpath /usr/share/java/bcprov.jar' \
              ' -storepass rogerthat' % (CURRENT_DIR, app_id)
    subprocess.check_output(command, shell=True)

    shutil.copy2(os.path.join(CURRENT_DIR, "truststore.bks"), file_path)


def create_trusstore_der(app_id, file_path):
    subprocess.check_output('cd %s; rm -f truststore.der' % CURRENT_DIR, shell=True)
    subprocess.check_output(
        'cd %s; openssl x509 -in %s/ca.cert.pem -out truststore.der -outform DER' % (CURRENT_DIR, app_id), shell=True)

    shutil.copy2(os.path.join(CURRENT_DIR, "truststore.der"), file_path)


def resize_image(src_img, dest_path, width, height):
    im1 = Image.open(src_img)
    im2 = im1.resize((width, height), Image.ANTIALIAS)  # best down-sizing filter
    _create_dir_if_not_exists(dest_path)
    im2.save(dest_path)


def with_background_color(src_file_path, dst_file_path, background_color):
    """Put the image on a background of `background_color`

    Args:
        image (Image)
        background_color (tuple): with the same mode of `image`
    """
    image = Image.open(src_file_path)
    back_image = Image.new(image.mode, image.size, parse_color(background_color))
    back_image.paste(image, (0, 0), mask=image)
    _create_dir_if_not_exists(dst_file_path)
    back_image.save(dst_file_path)


def increase_canvas(src_img, dest_path, width, height):
    im1 = Image.open(src_img)
    im2 = Image.new("RGBA", (width, height))
    x = int((width - im1.size[0]) / 2)
    y = int((height - im1.size[1]) / 2)

    im2.paste(im1, (x, y, x + im1.size[0], y + im1.size[1]))
    _create_dir_if_not_exists(dest_path)
    im2.save(dest_path)


def copytree(src, dst, symlinks=False, ignore=None):
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if not os.path.isdir(dst):  # This one line does the trick
        os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                # Will raise a SpecialFileError for unsupported file types
                shutil.copy2(srcname, dstname)
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error, err:
            errors.extend(err.args[0])
        except EnvironmentError, why:
            errors.append((srcname, dstname, str(why)))
    try:
        shutil.copystat(src, dst)
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error, errors


def get_license_header():
    with open(os.path.join(CURRENT_DIR, '..', 'res', 'apache_license.txt')) as f:
        license_text = f.read()
        return '/*\n%s\n */' % '\n'.join([' * ' + l for l in license_text.splitlines()])


def parse_color(color):
    m = re.match("^#?([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})$", color)
    if not m:
        raise ValueError("%s is not a valid color." % color)
    return tuple(map(lambda x: int(x, 16), m.groups()))


def recolor_png(png_bytes, source_color, target_color):
    def map_color(row, png_details):
        i = iter(row)
        if png_details['alpha']:
            return itertools.chain(*(target_color + b[3:] if b[:3] == source_color else b for b in itertools.izip(i, i, i, i)))
        else:
            return itertools.chain(*(target_color if b == source_color else b for b in itertools.izip(i, i, i)))

    r = png.Reader(file=StringIO(str(png_bytes)))
    p = r.read()
    c = p[2]
    f = StringIO()
    w = png.Writer(**p[3])
    w.write(f, [map_color(row, p[3]) for row in c])
    return f.getvalue()


def create_background(src_file_path, dst_file_path):
    '''Generate an image that can be used for repeating background (1px high) based on a given image.'''
    img = Image.open(src_file_path)
    w, h = img.size
    img.crop((0, h - 1, w, h)).save(dst_file_path)


def clamp(val, minimum=0, maximum=255):
    if val < minimum:
        return minimum
    if val > maximum:
        return maximum
    return val


def colorscale(hexstr, scalefactor):
    """
    Scales a hex string by ``scalefactor``. Returns scaled hex string.

    To darken the color, use a float value between 0 and 1.
    To brighten the color, use a float value greater than 1.

    # >>> colorscale("#DF3C3C", .5)
    #6F1E1E
    # >>> colorscale("#52D24F", 1.6)
    #83FF7E
    # >>> colorscale("#4F75D2", 1)
    #4F75D2
    """
    warnings.warn('Use lighten_color or darken_color instead', DeprecationWarning)

    hexstr = hexstr.strip('#')

    if scalefactor < 0 or len(hexstr) != 6:
        return hexstr

    r, g, b = int(hexstr[:2], 16), int(hexstr[2:4], 16), int(hexstr[4:], 16)

    r = clamp(r * scalefactor)
    g = clamp(g * scalefactor)
    b = clamp(b * scalefactor)

    return "#%02x%02x%02x" % (r, g, b)


# See https://medium.com/@anthony.st91/darken-or-lighten-a-color-in-android-ae70b63a249e
def lighten_color(color, value):
    hsl = rgb_to_hsl(color)
    hsl[2] += value
    # Increases the luminance of the colors
    hsl[2] = max(0.0, min(hsl[2], 1.0))
    return hsl_to_rgb(hsl)


def darken_color(color, value):
    hsl = rgb_to_hsl(color)
    hsl[2] -= value
    # Increases the luminance of the colors
    hsl[2] = max(0.0, min(hsl[2], 1.0))
    return hsl_to_rgb(hsl)


# Port from android.support.v4.graphics.ColorUtils

def rgb_to_hsl(rgb):
    rgb = rgb.strip('#')
    rf, gf, bf = int(rgb[:2], 16) / 255.0, int(rgb[2:4], 16) / 255.0, int(rgb[4:], 16) / 255.0

    maximum = max(rf, max(gf, bf))
    minimum = min(rf, min(gf, bf))
    delta = maximum - minimum

    l = (maximum + minimum) / 2.0

    if maximum == minimum:
        # Monochromatic
        h = s = 0.0
    else:
        if maximum == rf:
            h = ((gf - bf) / delta) % 6.0
        elif maximum == gf:
            h = ((bf - rf) / delta) + 2.0
        else:
            h = ((rf - gf) / delta) + 4.0

        s = delta / (1.0 - abs(2.0 * l - 1.0))

    h = h * 60.0 % 360
    if h < 0:
        h += 360

    hsl = [0, 0, 0]
    hsl[0] = constrain(h, 0.0, 360.0)
    hsl[1] = constrain(s, 0.0, 1.0)
    hsl[2] = constrain(l, 0.0, 1.0)
    return hsl


def constrain(amount, low, high):
    if amount < low:
        return low
    else:
        if amount > high:
            return high
        return amount


def hsl_to_rgb(hsl):
    h, s, l = hsl
    c = (1.0 - abs(2 * l - 1.0)) * s
    m = l - 0.5 * c
    x = c * (1.0 - abs((h / 60.0 % 2.0) - 1.0))

    hue_segment = int(h / 60)

    r = 0
    g = 0
    b = 0

    if hue_segment == 0:
        r = round(255 * (c + m))
        g = round(255 * (x + m))
        b = round(255 * m)
    elif hue_segment == 1:
        r = round(255 * (x + m))
        g = round(255 * (c + m))
        b = round(255 * m)
    elif hue_segment == 2:
        r = round(255 * m)
        g = round(255 * (c + m))
        b = round(255 * (x + m))
    elif hue_segment == 3:
        r = round(255 * m)
        g = round(255 * (x + m))
        b = round(255 * (c + m))
    elif hue_segment == 4:
        r = round(255 * (x + m))
        g = round(255 * m)
        b = round(255 * (c + m))
    elif hue_segment in (5, 6):
        r = round(255 * (c + m))
        g = round(255 * m)
        b = round(255 * (x + m))

    r = constrain(r, 0, 255)
    g = constrain(g, 0, 255)
    b = constrain(b, 0, 255)

    return "#%02x%02x%02x" % (r, g, b)
