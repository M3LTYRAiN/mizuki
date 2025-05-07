
from disnake.ext import commands
import disnake
from bot import bot, level_roles, save_level_role

@bot.slash_command(name="역할설정-레벨", description="레벨에 따른 역할을 설정하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할설정_레벨(
    inter: disnake.ApplicationCommandInteraction,
    역할30: disnake.Role = commands.Param(description="레벨 30에서 부여할 역할"),
    역할50: disnake.Role = commands.Param(description="레벨 50에서 부여할 역할"),
    역할70: disnake.Role = commands.Param(description="레벨 70에서 부여할 역할"),
    역할90: disnake.Role = commands.Param(description="레벨 90에서 부여할 역할"),
    역할100: disnake.Role = commands.Param(description="레벨 100에서 부여할 역할")
):
    guild_id = inter.guild.id
    
    # 역할 저장
    save_level_role(guild_id, 30, 역할30.id)
    save_level_role(guild_id, 50, 역할50.id)
    save_level_role(guild_id, 70, 역할70.id)
    save_level_role(guild_id, 90, 역할90.id)
    save_level_role(guild_id, 100, 역할100.id)
    
    # 확인 메시지 생성
    embed = disnake.Embed(
        title="✅ 레벨 역할 설정 완료",
        description="다음과 같이 레벨별 역할이 설정된 것이다.",
        color=disnake.Color.green()
    )
    
    embed.add_field(name="레벨 30", value=역할30.mention, inline=True)
    embed.add_field(name="레벨 50", value=역할50.mention, inline=True)
    embed.add_field(name="레벨 70", value=역할70.mention, inline=True)
    embed.add_field(name="레벨 90", value=역할90.mention, inline=True)
    embed.add_field(name="레벨 100", value=역할100.mention, inline=True)
    
    embed.set_footer(text="레벨업 시 해당 역할이 자동으로 부여되는 것이다.")
    
    await inter.response.send_message(embed=embed, ephemeral=True)