import asyncio
from os import environ as env
from logging import basicConfig, INFO
from math import ceil
from typing import Optional

from pyrogram import Client, idle, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

import aiohttp
import aiofiles
import ujson
#import uvloop
# uncomment if uvloop works for you
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
basicConfig(level=INFO)
app = Client(
    session_name="test",
    api_id=int(env.get("TELEGRAM_API_ID")),
    api_hash=env.get("TELEGRAM_API_HASH"),
    bot_token=env.get("TELEGRAM_BOT_TOKEN"),
)


DANBOORU_URL="https://danbooru.donmai.us"
PER_PAGE_POST_LIMIT=200
RESULT_LIMIT=10
PAGE_LIMIT=1000
POST_LIMIT=PER_PAGE_POST_LIMIT*PAGE_LIMIT
MASTER_QUEUE=asyncio.Queue(maxsize=27)
SPLITTER="--"


class DanbooruPageData:
    def __init__(
                self, *
                page_range: range,
                queue: asyncio.queues.Queue,
                master_queue: asyncio.queues.Queue,
            ) -> None:
        self.page_range = page_range
        self.queue = queue
        self.master_queue = master_queue


async def get_data(
            url: str, params: dict,
            session: aiohttp.client.ClientSession,
            page_data,
        ) -> None:
    """
    Fires session.get()
    Puts json from response in queue

    Common Exceptions:
        500: Internal Error,
            weird DB configuration,
            fires get_data() recursively
        429: Too Many Requests,
            lower maxlimit of MASTER_QUEUE
    """
    try:
        async with session.get(f"{url}", params=params) as resp:
            await page_data.queue.put(await resp.json(loads=ujson.loads))
    except aiohttp.errors.ClientResponseError as e:
        if e.status == 500:
            return await get_data(url, params, session, page_data)
        raise(e)


async def async_task_setter(
            url: str, params: dict,
            session: aiohttp.client.ClientSession,
            page_data,
        ) -> None:
    """
    Puts tasks in master_queue,
    fires get_data()
    """
    for page in page_data.page_range:
        params.update({"page": page})
        await page_data.master_queue.put(
            asyncio.create_task(
                get_data(url, params.copy(),
                    session, page_data)
            )
        )
    await page_data.master_queue.put(None)


async def async_task_getter(page_data) -> None:
    """
    waits on a task taken from MASTER_QUEUE
    """
    while True:
        task = await page_data.master_queue.get()
        if task is None:
            return
        await asyncio.wait({task})


async def crawler(
            url: str, *,
            params: Optional[dict] = None,
            page_data = None,
        ) -> Optional[aiohttp.client_reqrep.ClientResponse]:
    """
    Passes ClientSession to async_task_setter
    Depending on iterable kwarg,
    uses master_queue as task limiter,
    fires async_task setter and getter
    Otherwise it fires a session.get()
    """
    async with aiohttp.ClientSession(
        json_serialize=ujson.dumps,
        raise_for_status=True
    ) as session:
        if page_data:
            if params is None:
                params={}
            tasks = [
                        asyncio.create_task(
                            async_task_setter(
                                url, params,
                                session, page_data)
                        ),
                        asyncio.create_task(
                            async_task_getter(page_data)
                        ),
                    ]
            await asyncio.gather(*tasks)
            await queue.put(None)
        else:
            async with session.get(url, params=params) as resp:
                if resp.status == 500:
                    return await get(url, range(
                            page, iterator.step,
                            iterator.stop)
                        )
                return await resp.json(loads=ujson.loads)


@app.on_message(filters.command("get"))
async def search(_, msg: Message) -> None:
    """
    Searches for name_or_alias_matches
    The InlineKeyboardButton's callback_data
    calls givemethesauce()
    """
    resp_json = await crawler(
        f"{DANBOORU_URL}/tags.json",
        params={
            "search[name_or_alias_matches]": msg.command[1],
            "limit": RESULT_LIMIT,
        },
    )
    keyb_data = [
        [
            InlineKeyboardButton(
                text=f"{post['name']}{SPLITTER}{post['post_count']}",
                callback_data=f"owo{SPLITTER}{post['name']}{SPLITTER}{post['post_count']}",
            )
        ]
        for post in resp_json if post['post_count'] != 0
    ]
    if keyb_data:
        await msg.reply_text(
            text="search results:",
            reply_markup=InlineKeyboardMarkup(keyb_data),
        )
    else: await msg.reply_text("Not found.")


async def extract_data(
            file: aiofiles.threadpool.text.AsyncTextIOWrapper,
            page_data,
        ) -> None:
    """
    Gets response from queue
    Extracts data from response
    Writes data to a file
    """
    while True:
        resp_json = await page_data.queue.get()
        if resp_json is None:
            return
        for post in resp_json:
            if isinstance(post, dict):
                file_url = post.get('file_url')
                if file_url:
                    await file.write(f"{file_url}\n")


@app.on_callback_query(filters.regex("^owo"))
async def givemethesauce(_, query: CallbackQuery) -> None:
    """
    Accessible using /get
    Makes sauce file in a TemporaryDirectory
    Fires of crawler() and extract_data()
    Replies the document containing sauce

    """
    name, page_count = query.data.split(SPLITTER)
    page_count = int(page_count)
    if page_count<=POST_LIMIT: page_count = PAGE_LIMIT
    else: page_count = ceil(page_count/POST_LIMIT)
    queue = asyncio.Queue()
    page_data=DanbooruPageData(
            page_range=range(post_count),
            queue=queue,
            master_queue=MASTER_QUEUE,
        )
    async with aiofiles.tempfile.TemporaryDirectory() as tempdir:
        async with aiofiles.open(
                f"{tempdir}/sauce-{name}.txt", 'w') as file:
            tasks = [
                        asyncio.create_task(crawler(
                            f"{DANBOORU_URL}/posts.json",
                            params={"tags": name, "limit": PER_PAGE_POST_LIMIT},
                            page_data=page_data,
                        )),
                        asyncio.create_task(
                            extract_data(file, page_data)),
                    ]
            await asyncio.gather(*tasks)
            await file.close()
            await query.message.reply_document(file.name)


app.run()
