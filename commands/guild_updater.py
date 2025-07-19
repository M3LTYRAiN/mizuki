import disnake
from disnake.ext import commands
from datetime import datetime
from database import guilds_col

def save_guild_info(guild):
    icon_url = guild.icon.url if guild.icon else None
    banner_url = guild.banner.url if hasattr(guild, "banner") and guild.banner else None

    result = guilds_col.update_one(
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
    )
    return result

@commands.slash_command(name="갱신", description="이 서버의 정보를 DB에 즉시 업로드하는 것이다.")
async def 갱신(inter: disnake.ApplicationCommandInteraction):
    guild = inter.guild
    save_guild_info(guild)

    embed = disnake.Embed(
        title="서버 정보 갱신 완료!",
        description="이 서버의 정보가 DB에 성공적으로 업로드된 것이다!",
        color=disnake.Color.green()
    )
    embed.add_field(name="서버 이름", value=guild.name, inline=True)
    embed.add_field(name="서버 ID", value=str(guild.id), inline=True)
    embed.add_field(name="멤버 수", value=str(guild.member_count), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if hasattr(guild, "banner") and guild.banner:
        embed.set_image(url=guild.banner.url)
    embed.set_footer(text="서버 정보가 최신 상태로 저장되었습니다.")

    await inter.response.send_message(embed=embed, ephemeral=True)
