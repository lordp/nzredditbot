import praw
from datetime import datetime, timezone
from disco.bot import Plugin, Config
from disco.types.message import MessageEmbed
from disco.bot.command import CommandLevels
import json
import textwrap
from terminaltables import AsciiTable
from pprint import pprint


class RNZBotConfig(Config):
    debug = False
    channels = {
        "newzealand": None,
        "auckland": None,
        "chch": None,
        "wellington": None,
        "thetron": None,
        "dunedin": None,
        "hawkesbay": None,
        "nelsonnz": None,
        "taranaki": None,
        "palmy": None,
        "bayofplenty": None,
        "blenheim": None,
        "westcoastnz": None,
        "queenstown": None,
        "stewartisland": None,
        "masterton": None,
        "invercargill": None,
    }

    flair_colours = {
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
    }

    default_flair_colour = "c2c2cf"

@Plugin.with_config(RNZBotConfig)
class RNZBotPlugin(Plugin):
    def __init__(self, bot, config):
        super(RNZBotPlugin, self).__init__(bot, config)
        self.current_daily = None
        self.chan_iter = None

    def load(self, ctx):
        super(RNZBotPlugin, self).load(ctx)
        try:
            with open("subreddits.json") as infile:
                self.config.channels = json.load(infile)
        except FileNotFoundError:
            self.log.info("Subreddit settings file not found (subreddits.json)")
            pass

        self.set_assigned_channels_iter()

    def unload(self, ctx):
        self.save_settings()
        super(RNZBotPlugin, self).unload(ctx)

    def save_settings(self):
        with open("subreddits.json", "w") as outfile:
            json.dump(self.config.channels, outfile)

    def set_assigned_channels_iter(self):
        assigned_channels = [item for item in self.config.channels if self.config.channels[item]]
        self.chan_iter = iter(assigned_channels)

        return len(assigned_channels) > 0

    @Plugin.schedule(30)
    def check_channels(self):
        try:
            subreddit = next(self.chan_iter)
        except StopIteration:
            if self.set_assigned_channels_iter():
                subreddit = next(self.chan_iter)
            else:
                subreddit = None

        if subreddit and self.config.channels[subreddit] is not None:
            channel = self.state.channels.get(self.config.channels[subreddit]["id"], None)
            if channel is not None:
                self.post_threads(subreddit, channel)
        elif subreddit is None:
            self.log.info("No subreddits have been assigned to any channels")
        else:
            self.log.info("Subreddit {} has not been assigned a channel".format(subreddit))

    def find(self, channel_id):
        return next((item for item in self.config.channels if self.config.channels[item] is not None and
                     self.config.channels[item]["id"] == channel_id), None)

    def get_embed(self, info):
        if info['flair'] is None or info['flair'].lower() not in self.config.flair_colours:
            colour = int(self.config.default_flair_colour, 16)
        else:
            colour = int(self.config.flair_colours.get(info['flair'].lower(), self.config.default_flair_colour), 16)

        embed = MessageEmbed()
        embed.title = textwrap.shorten(u"[{}] {}".format(
            info["flair"], info["title"]
        ), width=256, placeholder="...")
        embed.url = "https://reddit.com{}".format(info["url"])
        embed.color = colour
        embed.set_thumbnail(url=info["thumbnail"])
        embed.set_author(name=info["author"], url="https://reddit.com/u/{}".format(info["author"]))
        embed.timestamp = datetime.fromtimestamp(info["time"], timezone.utc).isoformat()

        return embed

    def post_threads(self, subreddit, channel):
        if channel is not None:
            self.log.info("Checking submissions for {}".format(subreddit))

            rnz = RNZBot(subreddit)
            submissions = rnz.get_submissions()
            for info in submissions:
                if info["is_daily"]:
                    self.current_daily = info
                embed = self.get_embed(info)
                channel.send_message(embed=embed)

    @Plugin.command("assign", "[subreddit:str]", level=CommandLevels.TRUSTED)
    def cmd_assign(self, event, subreddit=None):
        if subreddit is None or subreddit not in self.config.channels:
            data = [
                ["Subreddit", "Channel"],
            ]

            for channel in sorted(self.config.channels):
                if self.config.channels[channel] is not None:
                    data.append([channel, self.config.channels[channel]["name"]])
                else:
                    data.append([channel, "None"])

            table_instance = AsciiTable(data)
            table_instance.justify_columns[3] = "right"
            table_instance.inner_column_border = False
            table_instance.outer_border = False

            event.msg.reply("```{}```".format(table_instance.table))
        else:
            self.config.channels[subreddit] = {"id": event.channel.id, "name": event.channel.name}
            event.msg.reply("Assigned /r/{} feed to this channel".format(subreddit))
            self.save_settings()

    @Plugin.command("unassign", level=CommandLevels.TRUSTED)
    def cmd_unassign(self, event):
        subreddit = self.find(event.channel.id)
        if subreddit in self.config.channels:
            self.config.channels[subreddit] = None
            event.msg.reply("Removed /r/{} feed from this channel".format(subreddit))
        else:
            event.msg.reply("This channel does not have a feed assigned")

    @Plugin.command("daily")
    def cmd_daily(self, event):
        if self.current_daily is None:
            event.msg.reply("Daily discussion thread not found")
        else:
            embed = self.get_embed(self.current_daily)
            event.msg.reply(embed=embed)

    @Plugin.command("details", "<user:str>", level=CommandLevels.TRUSTED)
    def cmd_details(self, event, user):
        u = [self.state.users[u] for u in self.state.users if self.state.users[u].username == user]
        channel = event.msg.author.open_dm()
        msg = "Name: {}, ID: {}, Discriminator: {}".format(u[0].username, u[0].id, u[0].discriminator)
        channel.send_message(msg)



class RNZBot:
    def __init__(self, subreddit):
        self.client = praw.Reddit("r-nz")
        self.subreddit_name = subreddit

        self.posted = []
        self.load_posted()

        self.sub_thumbnail = "https://b.thumbs.redditmedia.com/LbhL2LHGo_LjcjnKj4YBmMf6aXdCJdNae2Kpx3A8OaI.png"

    def load_posted(self):
        try:
            with open("rnz-threads-{}.json".format(self.subreddit_name)) as infile:
                self.posted = json.load(infile)
        except FileNotFoundError:
            self.posted = []

    def save_posted(self):
        posted = sorted(self.posted, key=lambda item: item["time"])
        with open("rnz-threads-{}.json".format(self.subreddit_name), "w") as outfile:
            json.dump(posted, outfile, indent=4)

    def find(self, channel_id):
        return next((True for item in self.posted if item["id"] == channel_id), False)

    def get_submissions(self):
        submissions = []
        missing_thumbnail = [
            "self", "default", ""
        ]

        subreddit = self.client.subreddit(self.subreddit_name)
        for submission in subreddit.new(limit=10):
            if not self.find(submission.id):
                if submission.thumbnail in missing_thumbnail:
                    thumbnail = self.sub_thumbnail
                else:
                    thumbnail = submission.thumbnail

                submissions.append({
                    "id": submission.id,
                    "title": submission.title,
                    "author": submission.author.name,
                    "time": submission.created_utc,
                    "flair": submission.link_flair_text,
                    "url": submission.permalink,
                    "thumbnail": thumbnail,
                    "is_daily": self.is_daily(submission)
                })

        self.posted += submissions
        self.save_posted()

        return sorted(submissions, key=lambda item: item["time"])

    def is_daily(self, submission):
        return submission.author.name == "AutoModerator" and self.subreddit_name == "newzealand" and \
            submission.link_flair_text == "Discussion"
