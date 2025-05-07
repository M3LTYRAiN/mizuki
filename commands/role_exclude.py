from disnake.ext import commands
import disnake
from bot import bot, save_excluded_role_data, server_excluded_roles

@bot.slash_command(name="역할제외", description="서버에서 역할을 제외하거나 해제하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할제외(
    inter: disnake.ApplicationCommandInteraction,
    action: str = commands.Param(choices=["추가", "제거"], description="추가 또는 제거"),
    role: disnake.Role = commands.Param(description="역할 선택"),
):
    guild_id = inter.guild.id

    if action == "추가":
        if guild_id not in server_excluded_roles:
            server_excluded_roles[guild_id] = []
        if role.id not in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].append(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에 추가된 것이다.", ephemeral=True)
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 이미 제외 목록에 있는 것이다.", ephemeral=True)
        save_excluded_role_data(guild_id, server_excluded_roles[guild_id])  # Save data to database
    elif action == "제거":
        if guild_id in server_excluded_roles and role.id in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].remove(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에서 제거된 것이다.", ephemeral=True)
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 제외 목록에 없는 것이다.", ephemeral=True)
        save_excluded_role_data(guild_id, server_excluded_roles[guild_id])  # Save data to database
