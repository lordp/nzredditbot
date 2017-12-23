import praw
from peewee import *
from datetime import datetime

db = SqliteDatabase("nzredditbot.db")
db.connect()


class Submission(Model):
    STATE_INITIAL = 0
    STATE_CHECKED = 1
    STATE_POSTED = 2

    subreddit = CharField()
    thing = CharField(unique=True)
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


if 'submission' not in db.get_tables():
    db.create_table(Submission)

client = praw.Reddit('r-nz')
subreddit = client.subreddit('newzealand')

missing_thumbnail = [
    "self", "default", ""
]

for submission in sorted(subreddit.new(limit=10), key=lambda item: item.created_utc):
    d = datetime.utcfromtimestamp(submission.created_utc)

    if submission.thumbnail in missing_thumbnail:
        thumbnail = "https://b.thumbs.redditmedia.com/LbhL2LHGo_LjcjnKj4YBmMf6aXdCJdNae2Kpx3A8OaI.png"
    else:
        thumbnail = submission.thumbnail

    flair = "Other" if submission.link_flair_text is None else submission.link_flair_text

    Submission(
        thing=submission.id,
        subreddit=subreddit,
        title=submission.title,
        author=submission.author.name,
        time=submission.created_utc,
        flair=flair,
        url=submission.permalink,
        thumbnail=thumbnail,
        is_daily=False
    ).save()

    print(submission.id, submission.title, submission.author.name)

print('-----------------------------------------')
subs = Submission.select().order_by(Submission.time.desc()).limit(10)
for sub in sorted(subs, key=lambda item: item.time):
    print(sub.thing, sub.title, sub.author, sub.flair)
