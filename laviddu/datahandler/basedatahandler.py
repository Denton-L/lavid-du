import markovify

class BaseDataHandler:
    def __init__(self):
        self._user_models = {}

        for user_id in self._get_saved_user_ids():
            self.read(user_id)

    def _get_saved_user_ids(self):
        raise NotImplementedError

    def _do_read(self, user_id):
        raise NotImplementedError

    def _do_write(self, user_id, data):
        raise NotImplementedError

    def read(self, user_id):
        self._user_models[user_id] = markovify.NewlineText.from_json(self._do_read(user_id))

    def write(self, user_id):
        self._do_write(user_id, self._user_models[user_id].to_json())

    def write_all(self):
        for user_id in self._user_models:
            self.write(user_id)

    def get_model(self, user_id):
        return (self._user_models[user_id]
                if user_id in self._user_models
                else None)

    def get_models(self, user_ids):
        return (self._user_models[user_id]
                for user_id in user_ids
                if user_id in self._user_models)

    def get_all_models(self):
        return self._user_models.values()

    def combine_models(self, user_id, user_model):
        self._user_models[user_id] = (
                markovify.combine([self._user_models[user_id], user_model])
                if user_id in self._user_models
                else user_model)
