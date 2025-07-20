import disnake
from bot import bot
from database import save_guild_info

@bot.slash_command(name="갱신", description="이 서버의 정보를 DB에 즉시 업로드하는 것이다.")
async def 갱신(inter: disnake.ApplicationCommandInteraction):
    await inter.response.defer(with_message=True)
    guild = inter.guild

    try:
        success = save_guild_info(guild)
        if success:
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
            await inter.edit_original_message(embed=embed)
        else:
            await inter.edit_original_message(content="❌ 정보를 저장하지 못한 것이다. 관리자에게 문의할 것!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await inter.edit_original_message(content=f"❌ 오류 발생: {str(e)}")
