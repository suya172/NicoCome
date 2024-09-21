from datetime import datetime, timedelta

import discord
from discord import app_commands, Embed
from discord.app_commands import describe
import pytz
from discord.ext import tasks

import re
from typing import Dict, Union
import config
import asyncio
import aiohttp

class VideoIdSyntaxError(Exception):
    """Idが不正である場合のエラー"""
    def __init__(self, message="ID syntax is invalid"):
        self.message = message
        super().__init__(self.message)

class Video():
    def __init__(self, id: str, title: Union[str, None] = None):
        try:
            if not id.startswith("sm"):
                raise VideoIdSyntaxError("ID syntax is invalid: " + id)
            
            _n = int(id[2:])

            if _n < 1:
                raise VideoIdSyntaxError("ID syntax is invalid: " + id)

            self.id = id
            self.title = title
        except ValueError:
            raise VideoIdSyntaxError("ID syntax is invalid: " + id)

videos: list[Video] = [Video("sm44115451"),Video("sm44103999"),Video("sm44096222"),Video("sm44089041"),Video("sm44082334")]
MAX_COMMENTS: int = 10

TOKEN: str = config.TOKEN
CHANNEL_ID: int = int(config.CHANNEL_ID) 
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def debug(message: str):
    print(datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S") + ' ' + message)

async def Send(message: Union[str, Embed], message_en: Union[str, None] = None):
    channel = client.get_channel(CHANNEL_ID)
    if message_en is None:
        if type(message) == str:
            message_en = message
        else:
            message_en = message.description
    if type(message) == str:
        await channel.send(message)
    else:
        await channel.send(embed=message)
    debug(message_en)

"""
https://zenn.dev/doma_itachi/articles/c448d4b6271d32
"""
class ThreadIdFetchError(Exception):
    """スレッドIDの取得に失敗した場合に発生するエラー"""
    def __init__(self, message="Failed to fetch thread ID"):
        self.message = message
        super().__init__(self.message)

class ThreadKeyFetchError(Exception):
    """スレッドキーの取得に失敗した場合に発生するエラー"""
    def __init__(self, message="Failed to fetch thread key"):
        self.message = message
        super().__init__(self.message)

class ThreadRequestBody:
    def __init__(self, thread_id: str, thread_key: str):
        self.params = {
            "targets": [
                {"id": thread_id, "fork": "owner"},
                {"id": thread_id, "fork": "main"},
                {"id": thread_id, "fork": "easy"}
            ],
            "language": "ja-jp"
        }
        self.threadKey = thread_key
        self.additionals = {}

class ThreadResponse:
    def __init__(self, data: Dict):
        self.meta = data['meta']
        self.data = data['data']

async def fetch_comments(url: str) -> ThreadResponse:
    endpoint = "https://public.nvcomment.nicovideo.jp/v1/threads"
    thread_id_regex = r'threadIds&quot;:\[\{&quot;id&quot;:(.*?),&quot;'
    thread_key_regex = r'{&quot;threadKey&quot;:&quot;(eyJ0eXAiOiJKV1Qi.*?)&quot'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            video_page = await response.text()

    thread_id_match = re.search(thread_id_regex, video_page)
    thread_key_match = re.search(thread_key_regex, video_page)

    if not thread_id_match:
        raise ThreadIdFetchError("ThreadId not found in the video page")
    if not thread_key_match:
        raise ThreadKeyFetchError("ThreadKey not found in the video page")

    thread_id = thread_id_match.group(1)
    thread_key = thread_key_match.group(1)

    payload = ThreadRequestBody(thread_id, thread_key)
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, json=payload.__dict__, headers={"x-frontend-id": "6"}) as response:
            thread_response = await response.json()

    return ThreadResponse(thread_response)

async def select_comments_after_datetime(response: ThreadResponse, after: datetime) -> list[str]:
    comments = []
    for comment in response.data['threads'][1]['comments']:
        comment_datetime = datetime.fromisoformat(comment['postedAt'])
        if comment_datetime > after:
            print(comment['body'])
            comments.append(comment['body'])
    return comments

async def NicoCome():
    await Send('コメント取得を開始', 'Start fetching comments')
    count: int = 0
    for video in videos:
        id = video.id
        url = f"https://www.nicovideo.jp/watch/{id}"
        try:
            print(f"Fetching comments for {url}")
            response = await fetch_comments(url)
            print(f"Status: {response.meta['status']}")
            print(f"Count: {response.data['threads'][1]['commentCount']}")
            comments = await select_comments_after_datetime(response, datetime.now(pytz.timezone("Asia/Tokyo")) - timedelta(days=1))
        except ThreadIdFetchError as e:
            Send(f"ThreadIdFetchError: {e}")
            break
        except ThreadKeyFetchError as e:
            Send(f"ThreadKeyFetchError: {e}")
            break
        except Exception as e:
            Send(f"An unexpected error occurred: {e}")
            break

        if len(comments) > MAX_COMMENTS:
            _embed = Embed(title=id,description='\n'.join(comments[:MAX_COMMENTS]) + '\n\n' + f'他{len(comments) - MAX_COMMENTS}件', color=0x006e54)
            count += 1
        elif len(comments) > 0:
            _embed = Embed(title=id,description='\n'.join(comments), color=0x66cdaa if count % 2 == 0 else 0x3cb371)
            count += 1
        await Send(_embed, f'{len(comments)} comments have been fetched')
    if count == 0:
        _embed = Embed(description='新着コメントはありません', color=0x4d4398)
        await Send(_embed, 'No new comments')

@tasks.loop(seconds=30)
async def check_time():
    now = datetime.now(pytz.timezone("Asia/Tokyo"))
    if now.hour == 0 and now.minute == 0:
        await Send('日付が変わりました', 'Date has changed')


@tree.command(name = 'add', description='新着コメントを取得する動画を登録')
@describe(id = '動画のID sm形式')
async def add(ctx: discord.Interaction, id: str):
    debug(f'Command: add {id}')
    try:
        video = Video(id)
        videos.append(video)
        await ctx.response.send_message(f'{id}を追加しました' + '\n' + f'https://www.nicovideo.jp/watch/{id}')
        debug(f'{id} has been added')
    except VideoIdSyntaxError as e:
        await ctx.response.send_message(f'{e}')
        debug(f'{e}') 

@tree.command(name = 'show', description='登録されている動画の一覧を表示')
async def show(ctx: discord.Interaction):
    debug('Command: show')
    _embed = Embed(title='動画の一覧', description='\n'.join([video.id for video in videos]), color=0x87ceeb)
    await ctx.response.send_message(embed=_embed)

@tree.command(name = 'remove', description='動画の登録を解除')
@describe(id = '動画のID sm形式')
async def remove(ctx: discord.Interaction, id: str):
    debug(f'Command: remove {id}')
    for video in videos:
        if video.id == id:
            videos.remove(video)
            await ctx.response.send_message(f'{id}の登録を解除しました')
            debug(f'{id} has been removed')
            return
    await ctx.response.send_message(f'{id}は登録されていません')
    debug(f'{id} is not registered')

@client.event
async def on_ready():
    await Send('ボットを起動', 'Bot has started')
    await client.change_presence(activity=discord.Game("ニコニコ動画"))
    await tree.sync()
    await Send('コマンドツリーを同期', 'Command tree has been synced')
    await NicoCome()
    check_time.start()

client.run(TOKEN)
