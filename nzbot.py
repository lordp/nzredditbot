import praw
from datetime import datetime, timezone
from disco.types.message import MessageEmbed
import textwrap
from peewee import *
import time
import requests
import json

db = SqliteDatabase("nzredditbot.db")
db.connect()


class Submission(Model):
    STATE_INITIAL = 0
    STATE_CHECKED = 1
    STATE_POSTED = 2

    subreddit = CharField()
    thing = CharField()
    title = CharField()
    author = CharField()
    time = DateTimeField()
    flair = CharField()
    url = CharField()
    thumbnail = CharField()
    is_daily = BooleanField()
    message_id = BigIntegerField(null=True)
    state = IntegerField(default=STATE_INITIAL)

    class Meta:
        database = db


class RNZBot:
    def __init__(self, subreddit):
        self.client = praw.Reddit("r-nz")
        self.subreddit_name = subreddit

        self.sub_thumbnail = "https://b.thumbs.redditmedia.com/LbhL2LHGo_LjcjnKj4YBmMf6aXdCJdNae2Kpx3A8OaI.png"

        self.flair_colours = {
            "politics": "E9987B",
            "advice": "e67367",
            "news": "CB7BC0",
            "discussion": "AB83E1",
            "picture": "73b1db",
            "sports": "60b8a7",
            "meta": "4ccd82",
            "travel": "f1d872",
            "other": "c2c2cf",
            "music": "2f2f2f",
            "civildefence": "005A9C",
            "ama": "0099CC",
            "kiwiana": "78A22F",
            "shitpost": "D4327C",
            "opinion": "FFB3BF",
            "longform": "53C68C",
            "māoritanga": "EA0027"
        }

        self.default_flair_colour = "c2c2cf"

        self.url = 'https://discordapp.com/api/webhooks/'
        self.hook_id = self.client.config.custom['hook_id']
        self.hook_token = self.client.config.custom['hook_token']

        self.limit = 0
        self.reset = 0
        self.remaining = 0

        self.get_submissions()
        self.post_submissions()

    def get_submissions(self):
        missing_thumbnail = [
            "self", "default", "spoiler", ""
        ]

        subreddit = self.client.subreddit(self.subreddit_name)
        for submission in subreddit.new(limit=10):
            print(submission.title)
            if submission.thumbnail in missing_thumbnail:
                thumbnail = self.sub_thumbnail
            else:
                thumbnail = submission.thumbnail

            flair = "Other" if submission.link_flair_text is None else submission.link_flair_text

            try:
                sub = Submission.get(thing=submission.id)

                sub.flair = flair
                if sub.state == Submission.STATE_INITIAL:
                    sub.state = Submission.STATE_CHECKED
            except DoesNotExist:
                sub = Submission(
                    thing=submission.id,
                    subreddit=self.subreddit_name,
                    title=submission.title,
                    author=submission.author.name,
                    time=submission.created_utc,
                    flair=flair,
                    url=submission.permalink,
                    thumbnail=thumbnail,
                    is_daily=False
                )

            sub.save()

    def post_submissions(self):
        submissions = Submission.select().where(
            Submission.state == Submission.STATE_CHECKED
        ).order_by(Submission.time.desc()).limit(10)

        full_url = self.url + self.hook_id + '/' + self.hook_token + '?wait=true'
        threads = [sub for sub in submissions]

        while len(threads) > 0:
            now = time.time()
            if self.remaining > 0 or now >= self.reset:
                submission = threads.pop()
                embed = self.get_embed(submission)
                content = {'embeds': [embed.to_dict()]}

                r = requests.post(full_url, json=content)
                self.limit = int(r.headers['X-RateLimit-Limit'])
                self.remaining = int(r.headers['X-RateLimit-Remaining'])
                self.reset = int(r.headers['X-RateLimit-Reset'])

                body = json.loads(r.content.decode('utf-8'))
                submission.message_id = body['id']
                submission.state = Submission.STATE_POSTED
                submission.save()
            else:
                print('Waiting for reset... {} seconds'.format(now - self.reset))
                time.sleep(5)

    def get_embed(self, info):
        flair = info.flair.replace('ā', 'a').lower()
        colour = int(self.flair_colours.get(flair, self.default_flair_colour), 16)

        embed = MessageEmbed()
        embed.title = textwrap.shorten(u"[{}] {}".format(
            info.flair, info.title
        ), width=256, placeholder="...")
        embed.url = "https://reddit.com{}".format(info.url)
        embed.color = colour
        embed.set_thumbnail(url=info.thumbnail)
        embed.set_author(name=info.author, url="https://reddit.com/u/{}".format(info.author))
        embed.timestamp = datetime.fromtimestamp(info.time, timezone.utc).isoformat()

        return embed


if __name__ == '__main__':
    bot = RNZBot('newzealand')
