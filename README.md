# lavid-du

A Slackbot that imitates your friends. Inspired by the dumb things said by
[@DavidLu1997](https://github.com/DavidLu1997).

## Usage

After the bot is added to your Slack channel, simply call it using `@Lavid Du imitate @<user>`.

If you would like to imitate multiple people, use `@Lavid Du imitate @<user1> @<user2> ...`.

Finally, to create a sentence based on all past data, use `@Lavid Du imitate @Lavid Du`.

## Dependencies

* Python 3 (tested on 3.6.2)
* [markovify](https://github.com/jsvine/markovify)
* [python-slackclient](https://github.com/slackapi/python-slackclient)
* [regex](https://pypi.python.org/pypi/regex)
