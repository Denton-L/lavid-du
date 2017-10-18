#!/usr/bin/env python3

import argparse
import json
import markovify
import regex
import signal
import slackclient
import time
import traceback

class LavidDu:
    SENTENCE_ATTEMPTS=1000

    def __init__(self, api_token, bot_api_token, data_file):
        self.slack_client = slackclient.SlackClient(api_token)
        self.bot_slack_client = slackclient.SlackClient(bot_api_token)
        self.data_file = data_file

        self.user_models = {}
        try:
            with open(self.data_file, 'r') as f:
                user_models = json.loads(f.read())
                for user in user_models:
                    self.user_models[user] = markovify.NewlineText.from_dict(user_models[user])
        except OSError:
            print('No data found. Starting from scratch.')

        self.user_id = self.get_user_id()
        self.running = False

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

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

    def get_user_id(self):
        return self.bot_slack_client.api_call('auth.test')['user_id']

    def send_message(self, channel, user_ids):
        collected_models = (
                list(self.user_models.values())
                if self.user_id in user_ids
                else [self.user_models[user_id]
                    for user_id in user_ids if user_id in self.user_models])

        if collected_models:
            final_model = (markovify.combine(collected_models)
                    if len(collected_models) > 1
                    else collected_models[0])
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

    def export_data(self):
        return {user: model.to_dict() for user, model in self.user_models.items()}

    def import_data(self, data):
        for user, model in data.items():
            self.combine_models(user, markovify.NewlineText.from_dict(model))

    def start(self):
        response_regex = regex.compile('<@%s> *imitate(?: *<@([A-Z0-9]+)>)+' % self.user_id)

        started = self.bot_slack_client.rtm_connect()
        if started:
            self.running = True
            old_data = None

            while self.running:
                try:
                    events = self.bot_slack_client.rtm_read()
                    for event in events:
                        print(event)

                        if event['type'] == 'message' and 'subtype' not in event:
                            text = event['text']

                            match = regex.match(response_regex, text)
                            if match:
                                self.send_message(event['channel'], match.captures(1))
                            else:
                                try:
                                    self.append_chain(event['user'], text)
                                except KeyError:
                                    # quick hack because it breaks when quotes are in the string
                                    print('KeyError caught')

                        new_data = json.dumps(self.export_data())
                        if old_data != new_data:
                            with open(self.data_file, 'w') as f:
                                f.write(new_data)
                            old_data = new_data

                    time.sleep(1)
                except:
                    print(traceback.format_exc())
        else:
            raise Exception('Unable to start!')

    def stop(self):
        self.running = False

    def handle_signal(self, signal, frame):
        self.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--settings', default='settings.json',
            help='The settings JSON to load from.')
    parser.add_argument('-d', '--data', default='data.json',
            help='The data JSON to load from.')
    parser.add_argument('--train-public', action='append',
            help='Get training data from a public channel.')
    parser.add_argument('--train-private', action='append',
            help='Get training data from a private channel.')
    args = parser.parse_args()

    with open(args.settings, 'r') as f:
        settings = json.loads(f.read())

    lavid_du = LavidDu(settings['api_key'], settings['bot_api_key'], args.data)

    if args.train_public:
        for channel in args.train_public:
            lavid_du.train(channel, True)

    if args.train_private:
        for channel in args.train_private:
            lavid_du.train(channel, False)

    lavid_du.start()
