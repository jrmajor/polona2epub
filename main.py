import codecs
import os
import xml.etree.ElementTree as xml
import zipfile
from xml.sax.saxutils import escape as escape_xml

import requests
from PIL import Image as image

entity = input('entity: ')
if entity == '':
    entity = 'OTE5MzY0MTY'

entity = requests.get('https://polona.pl/api/entities/' + entity, params={format: 'json'})
if entity.status_code != 200:
    print(str(entity.status_code) + ': ' + entity.json()['detail'])
    exit()
else:
    print(str(entity.status_code) + ': Found')

entity = entity.json()

print()

print('slug:      ' + entity['slug'])
print('title:     ' + str(entity['title']))
print('creator:   ' + str(entity['creator']))
print('published: ' + str(entity['publisher']) + ', ' + str(entity['publish_place']) + ', ' + str(entity['date_descriptive']))

print()

total = len(entity['scans'])
print('pages: ' + str(total))

print()
s_crop = input('crop (y/n): ')
if s_crop == 'y':
    s_ign_img = input('ignore images when cropping (y/n): ')
print()

path = os.path.join(os.path.dirname(__file__), entity['slug'])
if os.path.exists(path):
    print('path already exists')
    exit()
os.mkdir(path)
os.mkdir(os.path.join(path, 'originals'))
if s_crop == 'y':
    os.mkdir(os.path.join(path, 'cropped'))

for index, scan in enumerate(entity['scans']):
    print('\rgetting page ' + str(index) + '/' + str(total), end='')
    url = scan['thumbnails'][-1]['url']
    stream = requests.get(url, stream=True)
    if stream.status_code == 200:
        with open(os.path.join(path, 'originals', str(index) + '.jpg'), 'wb') as file:
            for chunk in stream.iter_content(1024):
                file.write(chunk)
    if s_crop == 'y':
        for resource in scan['resources']:
            if resource['mime'] == 'text/xml-alto':
                ocr_url = resource['url']
        if 'ocr_url' in locals():
            ocr = requests.get(ocr_url)
            if ocr.status_code == 200:
                tree = xml.fromstring(ocr.content)
                page_width = int(tree[2][0][0].attrib['WIDTH'])
                page_height = int(tree[2][0][0].attrib['HEIGHT'])
                cords = [page_width/2-1, page_height/2-1, page_width/2+1, page_height/2+1] # l t r b
                for block in tree[2][0][0]:
                    if s_ign_img != 'y' and (block.tag[42:] == "Illustration" or block.tag[42:] == "GraphicalElement"):
                        continue
                    block_hpos = int(block.attrib['HPOS'])
                    block_vpos = int(block.attrib['VPOS'])
                    block_width = int(block.attrib['WIDTH'])
                    block_height = int(block.attrib['HEIGHT'])
                    if cords[0] > block_hpos: # l
                        cords[0] = block_hpos
                    if cords[1] > block_vpos: # t
                        cords[1] = block_vpos
                    if cords[2] < block_hpos + block_width: # r
                        cords[2] = block_hpos + block_width
                    if cords[3] < block_vpos + block_height: # b
                        cords[3] = block_vpos + block_height
                    crop_data = True
                if 'crop_data' in locals():
                    image_obj = image.open(os.path.join(path, 'originals', str(index) + '.jpg'))
                    real_dimensions = image_obj.size
                    crop_scale = (real_dimensions[0] / page_width, real_dimensions[1] / page_height)
                    cords[0] = cords[0] * crop_scale[0]
                    cords[1] = cords[1] * crop_scale[1]
                    cords[2] = cords[2] * crop_scale[0]
                    cords[3] = cords[3] * crop_scale[1]
                    cords[0] = cords[0] - real_dimensions[0] * 0.02
                    cords[1] = cords[1] - real_dimensions[0] * 0.02
                    cords[2] = cords[2] + real_dimensions[0] * 0.02
                    cords[3] = cords[3] + real_dimensions[0] * 0.02
                    if cords[0] < 0:
                        cords[0] = 0
                    if cords[1] < 0:
                        cords[1] = 0
                    if cords[2] > real_dimensions[0]:
                        cords[2] = real_dimensions[0]
                    if cords[3] > real_dimensions[1]:
                        cords[3] = real_dimensions[1]
                    cropped_image = image_obj.crop(tuple(cords))
                    cropped_image.save(os.path.join(path, 'cropped', str(index) + '.jpg'))
            else:
                print('\rfailed to get ocr for page ' + str(index) + '/' + str(total))

print()
print('\rall pages downloaded')
print()
input('please, review scans')
print()

print('creating opf...', end='')
with codecs.open(os.path.join(path, 'content.opf'), 'w', encoding='utf8') as file:
    file.write("<?xml version='1.0' encoding='utf-8'?>" + '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf"><dc:title>' + escape_xml(str(entity['title'])) + '</dc:title><dc:creator opf:role="aut" opf:file-as="' + escape_xml(str(entity['creator'])) + '">' + escape_xml(str(entity['creator_name'])) + '</dc:creator><dc:date opf:event="publication">' + escape_xml(str(entity['date_descriptive'])) + '</dc:date></metadata><manifest><item href="part1.html" id="part1" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="part1"/></spine><guide><reference type="text" title="Początek" href="part1.html"/><reference href="0.jpg" type="cover" title="Okładka"/></guide></package>')
print('\ropf created    ')

print('creating html...', end='')
with codecs.open(os.path.join(path, 'part1.html'), 'w', encoding='utf8') as file:
    img = ''
    if s_crop == 'y':
        path_to_photos = os.path.join(path, 'cropped')
    else:
        path_to_photos = os.path.join(path, 'originals')
    for root, dirs, images in os.walk(path_to_photos):
        images.sort()
        images.sort(key=len)
        for image in images:
            img = img + '<img src="' + image + '"/>'
    file.write("<?xml version='1.0' encoding='utf-8'?>" + '<!DOCTYPE><html><head><meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8"/></head><body><div id="book-text" style="text-align: center;">' + img + '</div></body></html>')
print('\rhtml created    ')

print('creating archive...', end='')
zipf = zipfile.ZipFile(entity['slug'] + '.zip', 'w', zipfile.ZIP_DEFLATED)
if s_crop == 'y':
    path_to_zip = os.path.join(path, 'cropped')
else:
    path_to_zip = os.path.join(path, 'originals')
for root, dirs, files in os.walk(path_to_zip):
    total = len(files)
    for index, file in enumerate(files):
        print('\rarchiving file ' + str(index) + '/' + str(total) + '   ', end='')
        zipf.write(os.path.join(root, file), arcname=os.path.join('OPS', file))
zipf.write(os.path.join(path, 'content.opf'), arcname=os.path.join('OPS', 'content.opf'))
zipf.write(os.path.join(path, 'part1.html'), arcname=os.path.join('OPS', 'part1.html'))
zipf.close()
print('\rarchive created       ')

print('renaming archive...', end='')
os.rename(os.path.join(os.path.dirname(__file__), entity['slug'] + '.zip'))
print('\rarchive renamed    ')

print('deleting temp files...', end='')
for root, dirs, files in os.walk(path):
    for file in files:
        os.remove(os.path.join(root, file))
os.rmdir(os.path.join(path, 'originals'))
if s_crop == 'y':
    os.rmdir(os.path.join(path, 'cropped'))
os.rmdir(path)
print('\rtemp files deleted        ')

print()

print('epub ready')
