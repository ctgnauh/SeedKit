#!/usr/bin/env python
# -*- coding: utf-8 -*-


import re
import zlib
import base64
import hashlib
import urllib
from argparse import ArgumentParser
import bencode


class Torrent(object):
    def __init__(self, bdict):
        self.bdict = bdict
        self.info = self.bdict['info']
        if self.onlyone_file_p():
            self.files = [self.get_name()]
        else:
            self.files = self.info['files']

    def set_sth(self, root, name, sth, utf8=False):
        if utf8:
            root[name+'.utf-8'] = sth
        else:
            if type(sth) is type(list()):
                sth = [i.decode('utf-8').encode(self.get_encoding())
                       for i in sth]
            else:
                sth = sth.decode('utf-8').encode(self.get_encoding())
            root[name] = sth

    def set_sth_smart(self, root, name, sth):
        if name in root:
            self.set_sth(root, name, sth)
        if name+'.utf-8' in root:
            self.set_sth(root, name, sth, True)

    def get_sth(self, root, name):
        if type(root.get(name)) is type(list()):
            return [i.decode(self.get_encoding()).encode('utf-8')
                    for i in root.get(name)]
        return root.get(name).decode(self.get_encoding()).encode('utf-8')

    def set_comment(self, text, utf8=False):
        self.set_sth(self.bdict, 'comment', text, utf8)

    def set_comment_smart(self, text):
        self.set_sth_smart(self.bdict, 'comment', text)

    def get_comment(self):
        return self.get_sth(self.bdict, 'comment')

    def set_encoding(self, encoding):
        self.bdict['encoding'] = encoding

    def get_encoding(self):
        return self.bdict.get('encoding')

    def set_name(self, name, utf8=False):
        self.set_sth(self.info, 'name', name, utf8)

    def set_name_smart(self, name):
        self.set_sth_smart(self.info, 'name', name)

    def get_name(self):
        return self.get_sth(self.info, 'name')

    def set_path(self, index, path, utf8=False):
        self.set_sth(self.files[index], 'path', path, utf8)

    def set_path_smart(self, index, path):
        self.set_sth_smart(self.files[index], 'path', path)

    def get_path(self, index):
        return self.get_sth(self.files[index], 'path')

    def total_file(self):
        return len(self.files)

    def onlyone_file_p(self):
        if 'files' not in self.info:
            return True
        return False

    def export(self):
        return self.bdict

    def gen_infohash(self):
        encoded_info = bencode.bencode(self.info)
        return hashlib.sha1(encoded_info).hexdigest()

    def to_magnet(self):
        infohash = self.gen_infohash().upper()
        name = 'Unnamed'
        if 'name' in self.info:
            name = self.get_name()
        # magnet:?xt=urn:btih:INFO_HASH&dn=NAME
        return 'magnet:?xt=urn:btih:%s&dn=%s' % (infohash, name)

    def _match_keywords(self, string, keywords):
        for keyword in keywords:
            if string.find(keyword) != -1 and \
                    keyword != '':
                return True
        return False

    def _rename_file(self, filename, ignore_types, ignore_keywords):
        splitname = filename.rsplit('.', 1)
        if len(splitname) == 1:
            splitname = (splitname, '')
        basename, filetype = splitname
        if (filetype not in ignore_types) and \
                (not self._match_keywords(filename, ignore_keywords)):
            newname = base64.b64encode(filename)
            if filetype != '':
                newname = newname + '.' + filetype
            return newname
        return filename

    def rename_shortcut(self, ignore_types=[], ignore_keywords=[],
                        comment='Replaced by SeedKit'):
        # 替换注释
        self.set_comment_smart(comment)
        # 替换文件名与路径
        if self.onlyone_file_p() is True:
            # 只有一个文件
            filename = self.get_name()
            newname = self._rename_file(filename,
                                        ignore_types,
                                        ignore_types)
            self.set_name(newname)
            if 'name.utf-8' in self.info:
                self.set_name(newname, True)
        else:
            # 多个文件
            for i in range(self.total_file()):
                newpath = []
                path = self.get_path(i)
                for filename in path:
                    newpath.append(self._rename_file(filename,
                                                     ignore_types,
                                                     ignore_keywords))
                self.set_path_smart(i, newpath)

    def _gen_line(self, name, depth, dir_p=False):
        space = ''
        line = ''
        sep = ''
        for i in range(depth):
            space += '|   '
        if dir_p:
            sep = '/'
        line = space + '|---' + name + sep
        return line

    def print_tree(self):
        paths = [i.get('path') for i in self.files]
        printed = []
        for path in paths:
            depth = len(path) - 1
            for element in path:
                current_depth = path.index(element)
                dir_p = False
                if element in printed:
                    continue
                if current_depth < depth:
                    printed.append(element)
                    dir_p = True
                print self._gen_line(element, current_depth, dir_p)


class Magnet(object):
    def __init__(self, magnet):
        self.magnet = magnet
        self.infohash = re.search('[\w\d]{40}', magnet).group()

    def _urllib_downloader(self, url):
        try:
            result = urllib.urlopen(url)
        except:
            return None
        return result

    def _save_torrent(self):
        # http://torcache.net/torrent/INFO_HASH.torrent
        url = 'http://torcache.net/torrent/%s.torrent' % self.infohash
        zip_file = self._urllib_downloader(url)
        try:
            unzip_file = zlib.decompress(zip_file.read(), 16+zlib.MAX_WBITS)
        except zlib.error:
            return None
        return unzip_file

    def to_torrent(self, path=''):
        f = open(self.infohash+'.torrent', 'w')
        result = self._save_torrent()
        if result is None:
            return 0
        f.write(result)
        f.close()
        return 1


def main():
    # args
    parser = ArgumentParser(usage='%(prog)s [OPTION] FILE')
    parser.add_argument('-t', default='', dest='types')
    parser.add_argument('-k', default='', dest='keywords')
    parser.add_argument('-c', default='', dest='comment')
    parser.add_argument('-o', default='', dest='outputname')
    parser.add_argument('-m', action='store_true', dest='to_magnet')
    parser.add_argument('-p', action='store_true', dest='print_tree')
    parser.add_argument('-M', action='store_true', dest='magnet')
    parser.add_argument('-f', action='store_true', dest='to_torrent')
    parser.add_argument('file')
    args = parser.parse_args()

    if args.magnet is False:
        # load torrent
        input_file = open(args.file, 'r').read()
        bdict = bencode.bdecode(input_file)
        torrent = Torrent(bdict)
        # convert torrent to magnet
        if args.to_magnet:
            print torrent.to_magnet()
            return 1
        # print tree
        if args.print_tree:
            torrent.print_tree()
            return 1
        # rename_shortcut
        keywords = args.keywords.split(' ')
        types = args.types.split(' ')
        if args.outputname == '':
            args.outputname = 'fixed_'+args.file
        if args.comment == '':
            torrent.rename_shortcut(types, keywords)
        else:
            torrent.rename_shortcut(types, keywords, args.comment)
        # write torrent
        output_file = open(args.outputname, 'w')
        output_file.write(bencode.bencode(torrent.export()))
        output_file.close()
        return 1
    else:
        # load magnet
        if args.to_torrent:
            magnet = args.file
            return Magnet(magnet).to_torrent()


if __name__ == "__main__":
    main()
