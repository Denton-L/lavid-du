import os
import os.path
import regex

from .basedatahandler import BaseDataHandler

class FileDataHandler(BaseDataHandler):
    JSON_REGEX = regex.compile('(?P<id>[0-9A-Z]+)\.json')

    def __init__(self, data_dir):
        self._data_dir = data_dir
        super().__init__()

    def _get_full_path(self, user_id):
        return os.path.join(self._data_dir, '%s.json' % user_id)

    def _get_saved_user_ids(self):
        for json_filename in os.listdir(self._data_dir):
            full_path = os.path.join(self._data_dir, json_filename)
            match = FileDataHandler.JSON_REGEX.fullmatch(json_filename)

            if match and os.path.isfile(full_path):
                yield match.group('id')

    def _do_read(self, user_id):
        with open(self._get_full_path(user_id), 'r') as f:
            return f.read()

    def _do_write(self, user_id, data):
        with open(self._get_full_path(user_id), 'w') as f:
            f.write(data)
