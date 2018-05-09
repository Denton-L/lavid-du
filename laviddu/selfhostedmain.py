#!/usr/bin/env python3

import argparse
import json
import time
import traceback
import urllib.error
import urllib.request

import laviddu

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
    parser.add_argument('--since', type=float,
            help='Get training data since a certain timestamp')
    args = parser.parse_args()

    with open(args.settings, 'r') as f:
        settings = json.loads(f.read())

    wait_for_internet()

    lavid_du = laviddu.LavidDu(settings['api_key'], settings['bot_api_key'], args.data)

    if args.train_public:
        for channel in args.train_public:
            lavid_du.train(channel, args.since, True)

    if args.train_private:
        for channel in args.train_private:
            lavid_du.train(channel, args.since, False)

    if args.train_public or args.train_private:
        lavid_du.export_all_data()
    else:
        lavid_du.start()
