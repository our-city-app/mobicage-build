# Copyright 2016 Mobicage NV
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
# @@license_version:1.1@@

import itertools
import os
import re
import shutil
import subprocess
from PIL import Image
from zipfile import ZipFile

from colour import Color

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


def create_button(destination_path, primary_color='red', secondary_color='green', width=200, height=50,
                  transparency=50):
    """
    Creates an image with a colour gradient changing from primary_color to secondary_color, with the top half being
     slightly transparant
    Args:
        destination_path (int): destination path
        primary_color (unicode): colour at the left of the image. Can be a hex code e.g #ff0000 or a colour name like 'red'
        secondary_color (unicode): colour at the right of the image. Can be a hex code e.g #ff0000 or a colour name like 'red'
        width (int): width of the image
        height (int): height of the image
        transparency (int): 0-255, how transparent the top half of the image should be
    """
    primary_color = Color(primary_color)
    secondary_color = Color(secondary_color)
    colours = list(primary_color.range_to(secondary_color, width))
    data = []
    for h in range(height):
        for w in range(width):
            r = int(colours[w].get_red() * 255)
            g = int(colours[w].get_green() * 255)
            b = int(colours[w].get_blue() * 255)
            data.append((r, g, b))
    img = Image.new('RGB', (width, height), 255)
    img.putdata(data)
    if transparency:
        draw_transparant_overlay(img, transparency)
    img.save(destination_path)


def draw_transparant_overlay(image, transparency):
    overlay = Image.new('RGBA', image.size, (255, 255, 255, transparency))
    offset = (0, -image.size[1] / 2)
    image.paste(overlay, offset, overlay)
