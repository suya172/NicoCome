from datetime import datetime, timedelta

import discord
import pytz
from discord.ext import tasks

import re
from typing import Dict, Union
import config
import asyncio

TOKEN = config.TOKEN
CHANNEL_ID = int(config.CHANNEL_ID) 
intents = discord.Intents.all()

client = discord.Client(intents=intents)

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

async def Send(message: str, message_en: Union[str, None] = None):
    if message_en is None:
        message_en = message
    channel = client.get_channel(CHANNEL_ID)
    await channel.send(message)
    print(datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S") + ' ' + message_en)

@client.event
async def on_ready():
    await Send('ボットを起動しました', 'Bot has started') 

if __name__ == '__main__':
    client.run(TOKEN)
