#!/usr/bin/env python3

import argparse
import collections
import json
import markovify
import os
import os.path
import regex
import signal
import slackclient
import time
import traceback
import urllib.error
import urllib.request

class LavidDu:
    SENTENCE_ATTEMPTS = 1000
    SLEEP_DELAY = 0.1
    PING_EVERY = 10
    PING_COUNTER_MAX = int(PING_EVERY / SLEEP_DELAY)

    def __init__(self, api_token, bot_api_token, data_dir):
        self.slack_client = slackclient.SlackClient(api_token)
        self.bot_slack_client = slackclient.SlackClient(bot_api_token)
        self.data_dir = data_dir

        self.user_models = {}

        json_regex = regex.compile('(?P<id>[0-9A-Z]+)\.json')

        for json_filename in os.listdir(self.data_dir):
            full_path = os.path.join(self.data_dir, json_filename)
            match = json_regex.fullmatch(json_filename)

            if match and os.path.isfile(full_path):
                with open(full_path, 'r') as f:
                    text = f.read()
                self.user_models[match.group('id')] = markovify.NewlineText.from_json(text)

        self.name_ids = self.get_user_ids()
        self.user_id = self.get_own_id()
        self.running = False

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def export_data(self, user):
        full_path = os.path.join(self.data_dir, '%s.json' % user)
        text = self.user_models[user].to_json()
        with open(full_path, 'w') as f:
            f.write(text)

    def combine_models(self, user_id, user_model):
        self.user_models[user_id] = (
                markovify.combine([self.user_models[user_id], user_model])
                if user_id in self.user_models
                else user_model)

    def train(self, channel, is_public=True):
        response = self.slack_client.api_call(
                '%s.history' % ('channels' if is_public else 'groups'),
                channel=channel,
                count=1000)

        print(response)
        user_models = {}

        for message in response['messages']:
            if message['type'] == 'message' and 'subtype' not in message:
                user_models.setdefault(message['user'], []).append(message['text'])

        for user in user_models:
            self.combine_models(user, markovify.NewlineText('\n'.join(user_models[user])))

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
                self.user_models.values()
                if self.user_id in user_ids
                else [self.user_models[user_id]
                    for user_id in user_ids if user_id in self.user_models])

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
        self.combine_models(user_id, user_model)

    def import_data(self, data):
        for user, model in data.items():
            self.combine_models(user, markovify.NewlineText.from_dict(model))

    def start(self):
        response_regex = regex.compile(
                '<@%s> *imitate(?: *(?:(?P<name>[0-9a-z][0-9a-z._-]*)|(?:<@(?P<id>[0-9A-Z]+)>)))+' %
                self.user_id)

        try:
            started = self.bot_slack_client.rtm_connect()
            if started:
                self.running = True
                ping_counter = LavidDu.PING_COUNTER_MAX

                while self.running:
                    events = self.bot_slack_client.rtm_read()
                    for event in events:
                        print(event)

                        if event['type'] == 'message' and 'subtype' not in event:
                            text = event['text']

                            match = regex.search(response_regex, text)
                            if match:
                                ids = match.captures('id') + [self.name_ids[name]
                                        for name in match.captures('name') if name in self.name_ids]
                                if ids:
                                    self.send_message(event['channel'], ids)
                            else:
                                try:
                                    user = event['user']
                                    self.append_chain(user, text)
                                    self.export_data(user)
                                except KeyError:
                                    # quick hack because this is thrown occasionally
                                    print('KeyError caught:', text)
                        elif event['type'] == 'user_change':
                            self.name_ids = self.get_user_ids()

                    if not ping_counter:
                        self.bot_slack_client.server.ping()
                        ping_counter = LavidDu.PING_COUNTER_MAX
                    ping_counter -= 1

                    time.sleep(LavidDu.SLEEP_DELAY)
            else:
                raise Exception('Unable to start!')

        except Exception:
            print(traceback.format_exc())

    def stop(self):
        self.running = False

    def handle_signal(self, signal, frame):
        self.stop()

def wait_for_internet():
    disconnected = True
    while disconnected:
        try:
            urllib.request.urlopen('https://slack.com/', timeout=1)
            print('Internet connection established')
            disconnected = False
        except urllib.error.URLError:
            print('Waiting for internet connection...')
            time.sleep(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--settings', default='settings.json',
            help='The settings JSON to load from.')
    parser.add_argument('-d', '--data', default='data/',
            help='The data directory to load from.')
    parser.add_argument('--train-public', action='append',
            help='Get training data from a public channel.')
    parser.add_argument('--train-private', action='append',
            help='Get training data from a private channel.')
    args = parser.parse_args()

    with open(args.settings, 'r') as f:
        settings = json.loads(f.read())

    wait_for_internet()

    lavid_du = LavidDu(settings['api_key'], settings['bot_api_key'], args.data)

    if args.train_public:
        for channel in args.train_public:
            lavid_du.train(channel, True)

    if args.train_private:
        for channel in args.train_private:
            lavid_du.train(channel, False)

    lavid_du.start()
