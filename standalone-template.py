from os import environ as env, cpu_count
from logging import basicConfig, INFO
from math import ceil

from pyrogram import Client, idle, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

import ujson
import aiohttp
from aiofiles.tempfile import TemporaryDirectory
from aiofiles import open


DANBOORU_URL = "https://danbooru.donmai.us"
basicConfig(level=INFO)
# maybe use ":memory:"
app = Client(
    session_name="test",
    api_id=int(env.get("TELEGRAM_API_ID")),
    api_hash=env.get("TELEGRAM_API_HASH"),
    bot_token=env.get("TELEGRAM_BOT_TOKEN"),
)


POST_LIMIT = 200
RESULT_LIMIT=10


async def get(url: str, *, params: dict=None, iterator: range=None):
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        if iterator:
            if params is None:
                params={}
            for page in iterator:
                params.update({"page": page})
                async with session.get(f"{url}", params=params) as resp:
                    if resp.status == 500:
                        async for resp in get(url, range(page, iterator.step, iterator.stop)):
                            yield resp
                    else:
                        yield resp
        else:
            async with session.get(url, params=params) as resp:
                if resp.status != 500:
                    yield resp


@app.on_message(filters.command("get"))
async def searchthestuff(_, msg: Message):
    async for resp in get(
        f"{DANBOORU_URL}/tags.json",
        params={"search[name_or_alias_matches]": msg.command[1], "limit": RESULT_LIMIT},
    ):
        keyb_data = [
            [
                InlineKeyboardButton(
                    text=f"{post['name']}--{post['post_count']}",
                    callback_data=f"owo--{post['name']}--{post['post_count']}",
                )
            ]
            for post in ujson.loads(await resp.text()) if post['post_count'] != 0
        ]
        await msg.reply_text(
            text="search results:",
            reply_markup=InlineKeyboardMarkup(keyb_data),
        )


@app.on_callback_query(filters.regex("^owo"))
async def givemethesauce(_, query: CallbackQuery):
    match = query.data.split("--")
    name = match[1]
    page_count = ceil(int(match[2])/POST_LIMIT) if int(match[2])<=200_000 else 1000 # 200_000 posts is danbooru limit, 1000 pages is max
    async with TemporaryDirectory() as tempdir:
        async with open(f"{tempdir}/sauce-{name}.txt", 'w') as file:
            async for resp in get(
                f"{DANBOORU_URL}/posts.json",
                params={"tags": name, "limit": POST_LIMIT},
                iterator=range(page_count)
            ):
                for post in ujson.loads(await resp.text()):
                    if isinstance(post, dict):
                        file_url = post.get('file_url')
                        if file_url:
                            await file.write(f"{file_url}\n")
            await file.close()
            await query.message.reply_document(file.name)


app.run()
