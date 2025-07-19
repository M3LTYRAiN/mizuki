import disnake
from disnake.ext import commands
from datetime import datetime, timezone
from database import save_guild_info

@commands.slash_command(name="갱신", description="이 서버의 정보를 DB에 즉시 업로드하는 것이다.")
async def 갱신(inter: disnake.ApplicationCommandInteraction):
    guild = inter.guild

    guild_info = {
        "guild_id": guild.id,  # int로 넘기는 것이 일반적
        "name": guild.name,
        "member_count": guild.member_count,
        "icon_url": guild.icon.url if guild.icon else None,
        "banner_url": guild.banner.url if guild.banner else None,
        "updated_at": datetime.now(timezone.utc),
        # "created_at"은 최초 생성 시만 필요하므로 생략 가능
    }

    save_guild_info(guild_info)

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
