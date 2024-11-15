import shutil
import requests
import json
import urllib.parse
from subprocess import check_output
from concurrent.futures import as_completed, ThreadPoolExecutor
import time
import os

TOKEN = ''


def assure_folder_exists(folder, root):
    full_path = os.path.join(root, folder)
    if os.path.isdir(full_path):
        pass
    else:
        os.mkdir(full_path)
    return full_path

# TODO: Replace with a named tuple
class File:
    def __init__(self, name, link):
        self.name = name
        self.link = link

    def __repr__(self):
        return '<F:{}>'.format(self.name)


class StickerDownloader:
    def __init__(self, token, session=None, multithreading=4):
        self.THREADS = multithreading
        self.token = token
        self.cwd = assure_folder_exists('downloads', root=os.getcwd())
        if session is None:
            self.session = requests.Session()
        else:
            self.session = session
        self.api = 'https://api.telegram.org/bot{}/'.format(self.token)
        verify = self._api_request('getMe', {})
        if verify['ok']:
            pass
        else:
            print('Invalid token.')
            exit()

    def _api_request(self, fstring, params):
        try:
            param_string = '?' + urllib.parse.urlencode(params)
            res = self.session.get('{}{}{}'.format(self.api, fstring, param_string))
            if res.status_code != 200:
                raise Exception
            res = json.loads(res.content.decode('utf-8'))
            if not res['ok']:
                raise Exception(res['description'])
            return res

        except Exception as e:
            print('API method {} failed. Error: "{}"'.format(fstring, e))
            return None

    def get_file(self, file_id):
        info = self._api_request('getFile', {'file_id': file_id})
        f = File(name=info['result']['file_path'].split('/')[-1],
                 link='https://api.telegram.org/file/bot{}/{}'.format(self.token, info['result']['file_path']))

        return f

    def get_sticker_set(self, name):
        """
        Get a list of File objects.
        :param name:
        :return:
        """
        params = {'name': name}
        res = self._api_request('getStickerSet', params)
        if res is None:
            return None
        stickers = res['result']['stickers']
        files = []
        print('Starting to scrape "{}" ..'.format(name))
        start = time.time()
        with ThreadPoolExecutor(max_workers=self.THREADS) as executor:
            futures = [executor.submit(self.get_file, i['file_id']) for i in stickers]
            for i in as_completed(futures):
                files.append(i.result())

        end = time.time()
        print('Time taken to scrape {} stickers - {:.3f}s'.format(len(files), end - start))
        print()

        sticker_set = {
            'name': res['result']['name'].lower(),
            'title': res['result']['title'],
            'files': files
        }
        return sticker_set

    def download_file(self, name, link, path):
        file_path = os.path.join(path, name)
        with open(file_path, 'wb') as f:
            res = self.session.get(link)
            f.write(res.content)

        return file_path

    def download_sticker_set(self, sticker_set):
        swd = assure_folder_exists(sticker_set['name'], root=self.cwd)
        download_path = assure_folder_exists('source', root=swd)
        downloads = []

        print('Starting download of "{}" into {}'.format(sticker_set['name'], download_path))
        start = time.time()
        with ThreadPoolExecutor(max_workers=self.THREADS) as executor:
            futures = [executor.submit(self.download_file, f.name, f.link, download_path) for f in sticker_set['files']]
            for i in as_completed(futures):
                downloads.append(i.result())

        end = time.time()
        print('Time taken to download {} stickers - {:.3f}s'.format(len(downloads), end - start))
        print()

        return downloads

    @staticmethod
    def convert_file(_input, _output_folder):
        file_name = "/" + os.path.basename(_input)
        if _input[-4:] == 'webp':
            command = 'ffmpeg -n -hide_banner -loglevel error -i "{}" "{}"'.format(_input, _output_folder + file_name[:-4] + "png")
        elif _input[-4:] == 'webm':
            command = 'ffmpeg -n -hide_banner -loglevel error -i "{}" "{}"'.format(_input, _output_folder + file_name[:-4] + "gif")
        else:
            print("Encountered an unknown file type. Copying as-is.")
            shutil.copy(_input, _output_folder)
            return
        check_output(command, shell=True)

    def convert_to_pngs(self, name):
        swd = assure_folder_exists(name, root=self.cwd)
        source_folder = assure_folder_exists('source', root=swd)
        dest_folder = assure_folder_exists('converted', root=swd)

        source_files = [os.path.join(source_folder, i) for i in os.listdir(source_folder)]
        png_files = []

        print('Converting stickers to pngs "{}"..'.format(name))
        start = time.time()
        with ThreadPoolExecutor(max_workers=self.THREADS) as executor:
            futures = [executor.submit(self.convert_file, _input, dest_folder)
                       for _input in source_files]
            for i in as_completed(futures):
                png_files.append(i.result())

        end = time.time()
        print('Time taken to convert {} stickers - {:.3f}s'.format(len(png_files), end - start))
        print()


if __name__ == "__main__":
    downloader = StickerDownloader(TOKEN)
    print('Welcome to Telegram Downloader..')
    names = []
    while True:
        name = input("Enter sticker_set url (leave blank to stop): ").strip()
        if name == '':
            break
        names.append(name.split('/')[-1])

    names = list(set(names)) # Deduplicate URLs

    for sset in names:
        print('=' * 60)
        _ = downloader.get_sticker_set(sset)
        if _ is None:
            continue
        print('-' * 60)
        _ = downloader.download_sticker_set(_)
        print('-' * 60)
        downloader.convert_to_pngs(sset)
