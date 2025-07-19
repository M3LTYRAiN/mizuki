# guild_updater.py

import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import UpdateOne
from discord import Guild
from database import guilds_col  # DB에서 불러옴

# 서버 정보 저장 함수
def update_guilds(bot):
    bulk_ops = []

    for guild in bot.guilds:
        icon_url = guild.icon.url if guild.icon else None
        banner_url = guild.banner.url if guild.banner else None

        bulk_ops.append(UpdateOne(
            {'guild_id': guild.id},
            {
                '$set': {
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon_url': icon_url,
                    'banner_url': banner_url,
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        ))

    if bulk_ops:
        guilds_col.bulk_write(bulk_ops)
    else:
        print("[GuildUpdater] No guilds found to update.")

# 스케줄러 설정
def setup_guild_updater(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_guilds, "interval", minutes=10, args=[bot])
    scheduler.start()
