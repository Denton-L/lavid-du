import collections
import regex
import signal
import slackclient
import time
import traceback

import markovify

class LavidDu:
    SENTENCE_ATTEMPTS = 1000
    SLEEP_DELAY = 0.1
    PING_EVERY = 10.0
    RESPONSE_REGEX_TEMPLATE = '<@%s> *imitate(?: *(?:(?P<name>[0-9a-z][0-9a-z._-]*)|(?:<@(?P<id>[0-9A-Z]+)>)))+'

    def __init__(self, api_token, bot_api_token, data_handler):
        self.slack_client = slackclient.SlackClient(api_token)
        self.bot_slack_client = slackclient.SlackClient(bot_api_token)
        self._data_handler = data_handler

        self.name_ids = self.get_user_ids()
        self.user_id = self.get_own_id()
        self.running = False
        self.response_regex = regex.compile(LavidDu.RESPONSE_REGEX_TEMPLATE % self.user_id)

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def export_all_data(self):
        self._data_handler.write_all()

    def train(self, channel, since, is_public=True):
        user_models = {}
        has_more = True
        last_timestamp = since or 0

        while has_more:
            response = self.slack_client.api_call(
                    '%s.history' % ('channels' if is_public else 'groups'),
                    channel=channel,
                    oldest=last_timestamp,
                    count=1000)
            print(response)

            for message in response['messages']:
                if (message['type'] == 'message'
                        and 'subtype' not in message):
                    user_models.setdefault(message['user'], []).append(message['text'])
            last_timestamp = response['messages'][0]['ts']
            has_more = since and response['has_more']

            if has_more:
                time.sleep(LavidDu.SLEEP_DELAY)

        for user in user_models:
            self._data_handler.combine_models(user, markovify.NewlineText('\n'.join(user_models[user])))

    def get_user_ids(self):
        members = self.slack_client.api_call('users.list')['members']
        return {
                **{member['profile']['display_name']: member['id'] for member in members},
                **{member['name']: member['id'] for member in members}
                }

    def get_own_id(self):
        return self.bot_slack_client.api_call('auth.test')['user_id']

    def send_message(self, channel, user_ids):
        id_counter = collections.Counter(
                self._data_handler.get_all_models()
                if self.user_id in user_ids
                else self._data_handler.get_models(user_ids))

        if id_counter:
            final_model = (markovify.combine(list(id_counter.keys()), list(id_counter.values()))
                    if len(id_counter) > 1
                    else next(iter(id_counter)))
            text = final_model.make_sentence(tries=LavidDu.SENTENCE_ATTEMPTS)
            if not text:
                print('Unable to create unique sentence.')
                text = final_model.make_sentence(test_output=False)
        else:
            text = 'I do not have data for anyone listed.'

        return self.slack_client.api_call(
                'chat.postMessage',
                channel=channel,
                text=text)

    def append_chain(self, user_id, text):
        user_model = markovify.NewlineText(text)
        self._data_handler.combine_models(user_id, user_model)

    def import_data(self, data):
        for user, model in data.items():
            self._data_handler.combine_models(user, markovify.NewlineText.from_dict(model))

    def process_event(self, event):
        if event['type'] == 'message' and 'subtype' not in event:
            text = event['text']

            match = self.response_regex.search(text)
            if match:
                ids = match.captures('id') + [self.name_ids[name]
                        for name in match.captures('name') if name in self.name_ids]
                if ids:
                    self.send_message(event['channel'], ids)
            else:
                try:
                    user = event['user']
                    self.append_chain(user, text)
                    self._data_handler.write(user)
                except KeyError:
                    # quick hack because this is thrown occasionally
                    print('KeyError caught:', text)
        elif event['type'] == 'user_change':
            self.name_ids = self.get_user_ids()

    def start(self):
        self.running = True
        last_ping = 0.0

        while self.running:
            started = self.bot_slack_client.rtm_connect(False)
            if not started:
                print('Unable to start. Retrying...')
                time.sleep(LavidDu.SLEEP_DELAY)
                continue

            try:
                while self.running:
                    events = self.bot_slack_client.rtm_read()
                    for event in events:
                        print(event)
                        self.process_event(event)

                    now = time.time()
                    if now - last_ping >= LavidDu.PING_EVERY:
                        self.bot_slack_client.server.ping()
                        last_ping = now

                    time.sleep(LavidDu.SLEEP_DELAY)

            except Exception:
                print(traceback.format_exc())

    def stop(self):
        self.running = False

    def handle_signal(self, signal, frame):
        self.stop()
